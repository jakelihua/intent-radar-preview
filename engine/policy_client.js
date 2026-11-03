// Same fact contract as policy.evaluate_facts; cross-language vectors run in CI.
const COMPETITOR_ALIASES = {
    'jira': 'atlassian jira',
    'confluence': 'atlassian confluence',
    'salesforce': 'salesforce crm',
    'newrelic': 'new relic',
    'clerk.dev': 'clerk',
    'hellosign': 'hellosign / dropbox sign',
    'dropbox sign': 'hellosign / dropbox sign',
    'twenty': 'twenty crm',
};
const INVALID_COMPETITOR_PLACEHOLDERS = new Set(['', '未知', '通用行业竞品', '同赛道传统竞品', 'none', 'unknown']);
function canonicalCompetitor(name) {
    const cleaned = String(name || '').trim().toLowerCase();
    if (!cleaned) return '';
    return COMPETITOR_ALIASES[cleaned] || cleaned;
}
function policyText(value) {
    return Array.isArray(value) ? value.map(x => String(x).trim()).join('；') : String(value || '').trim();
}
function sellerSnapshot(profile = {}) {
    profile = (profile && typeof profile === 'object' && !Array.isArray(profile)) ? profile : {};
    const rawTargets = Array.isArray(profile.target_competitors) ? profile.target_competitors : [];
    const normTargets = Array.from(new Set(rawTargets.map(canonicalCompetitor).filter(Boolean))).sort();
    return ['brand_name', 'actor_role', 'approved_capabilities', 'known_limitations', 'cta_link']
        .map(k => policyText(profile[k])).concat([normTargets]);
}
function policyTime(value) {
    if (typeof value !== 'string' || !/(Z|\+00:00)$/.test(value)) return NaN;
    const t = Date.parse(value);
    return Number.isFinite(t) && new Date(t).toISOString().slice(0,19) === value.slice(0,19) ? t : NaN;
}
function evaluatePolicyFacts(facts, profile = null, nowMs = Date.now()) {
    facts = (facts && typeof facts === 'object' && !Array.isArray(facts)) ? facts : {};
    profile = (profile && typeof profile === 'object' && !Array.isArray(profile)) ? profile : {};
    const rawTargets = Array.isArray(profile.target_competitors) ? profile.target_competitors : [];
    const targets = rawTargets.map(canonicalCompetitor).filter(Boolean);
    const complete = !!(policyText(profile.brand_name) && policyText(profile.actor_role) && policyText(profile.approved_capabilities) && targets.length && !targets.includes('*'));
    const entities = String(facts.competitor || '').split('/').map(canonicalCompetitor).filter(x => x && !INVALID_COMPETITOR_PLACEHOLDERS.has(x));
    const compatible = !!(complete && entities.length && entities.some(x => targets.includes(x)));
    const rawReviews = (profile.reviews && typeof profile.reviews === 'object' && !Array.isArray(profile.reviews)) ? profile.reviews : {};
    const rawRev = rawReviews[facts.source_id];
    const review = (rawRev && typeof rawRev === 'object' && !Array.isArray(rawRev)) ? rawRev : {};
    const age = nowMs - policyTime(review.reviewed_at || '');
    const current = !!(age >= 0 && age <= 30 * 86400000 && review.source === facts.source &&
        review.content_hash === facts.content_hash && JSON.stringify(review.seller_snapshot) === JSON.stringify(sellerSnapshot(profile)) &&
        policyText(review.reviewer) && policyText(review.evidence));
    const s1 = facts.pain_verified === true;
    const s2 = s1 && facts.evaluation_verified === true;
    const fit = current ? review.fit : 'pending';
    const s3 = s2 && compatible && fit === 'supported';
    const publishedAge = nowMs - policyTime(facts.published_at || '');
    const live = facts.dataset_kind === 'live_production' && facts.delivery_eligible === true && facts.content_complete === true && publishedAge >= 0 && publishedAge <= 30 * 86400000;
    let contact = false;
    try { const u = new URL(review.contact_url); contact = typeof review.contact_url === 'string' && !/[\s<>"\\]/.test(review.contact_url) && ['http:', 'https:'].includes(u.protocol) && !!u.hostname && !u.username && !u.password; } catch (_) {}
    const actionable = current && review.authority_confirmed === true && contact && !!policyText(review.contact_evidence);
    const s4 = !!(s3 && live && actionable);
    const passed = [!!s1, !!s2, !!s3, s4];
    const firstFailure = passed.indexOf(false);
    const blocked = !s2 || (!!policyText(profile.brand_name) && complete && !compatible) || (current && fit === 'unsupported');
    return { passed, contiguous: firstFailure < 0 ? 4 : firstFailure, compatible: !!compatible,
        review_current: current, live: !!live,
        policy_status: blocked ? 'blocked' : s3 && actionable ? 'approved_recommendation' : 'neutral_inquiry_only',
        can_outreach: !blocked, can_recommend_product: !!(s3 && actionable && !blocked), allow_webhook_push: !!(s4 && !blocked) };
}
