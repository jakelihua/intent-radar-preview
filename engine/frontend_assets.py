"""
Frontend JS Controller, Pure-JS OpenXML (.xlsx) Generator, and Internal BD Playbook Renderer (v3.1).
Resolves Audit Round-2 Findings:
- Finding #3 & #6: Unified 4-stage sequential qualification & outreach policy ('blocked' | 'neutral_inquiry_only' | 'approved_recommendation')
  mirrored identically in JS; requires explicit `actor_role`, `target_competitors` (no '*' wildcard default), and `approved_capabilities`.
- Finding #4: Separates `candidate_alternatives` (author verbatim mentions) from `system_recommended_alternatives` (system suggestions)
  and renders per-field verbatim evidence snippets on every provenance card.
- Finding #10: `memoryStatusStore` is initialized once from `localStorage` and serves as the authoritative session truth
  so quota errors on subsequent writes never revert to stale `localStorage` values.
- P2 Fixes:
  1. Restores focus after `closeDrawer()` by querying the newly rendered button for `lastFocusedTrigger.leadId` in live DOM.
  2. Blocks `/` search shortcut when modal or drawer is open.
  3. Uses `role="group"` + `aria-pressed="true|false"` on Split View buttons instead of mismatched `listbox`/`button`.
  4. Checks `/^[\t\r\n]/` and `/^[\s]*[=+\-@]/` BEFORE `\r` normalization in CSV sanitization (`sanitizeCsvCell`), separates XLSX `inlineStr` handling, clamps 32,767-char Excel cell limit, and adds `<cellStyles><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>` in `xl/styles.xml`.
"""

from datetime import datetime
from typing import Dict, List


CLIENT_WORKBENCH_JS = r"""
// ============================================================================
// 1. Security, URL Validation & Separated CSV / XLSX Sanitization
// ============================================================================
function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function sanitizeUrl(url) {
    if (!url) return '#';
    try {
        const parsed = new URL(String(url).trim(), window.location.origin);
        if (parsed.protocol === 'http:' || parsed.protocol === 'https:') {
            return parsed.href;
        }
    } catch (e) {
        return '#';
    }
    return '#';
}

// OWASP CSV Formula Injection Prevention:
// Checks leading \t, \r, \n OR optional whitespace followed by =, +, -, @, \t, \r BEFORE normalizing \r!
function sanitizeCsvCell(val) {
    if (val === null || val === undefined) return '';
    const raw = String(val);
    const needsPrefix = /^[\t\r\n]/.test(raw) || /^[\s]*[=+\-@\t\r]/.test(raw);
    const normalized = raw.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
    return needsPrefix ? ("'" + normalized) : normalized;
}

// Backward-compatible alias for unit tests
function sanitizeSpreadsheetCell(val) {
    return sanitizeCsvCell(val);
}

// XLSX inlineStr text normalizer (enforces Excel's 32,767 char cell limit without adding literal single quotes)
const EXCEL_MAX_CELL_CHARS = 32767;
function normalizeXlsxCellText(val) {
    if (val === null || val === undefined) return '';
    let str = String(val).replace(/\r\n/g, '\n').replace(/\r/g, '\n');
    if (str.length > EXCEL_MAX_CELL_CHARS) {
        str = str.slice(0, EXCEL_MAX_CELL_CHARS - 15) + '...[TRUNCATED]';
    }
    return str;
}

// ============================================================================
// 2. Authoritative Session State Store & 7-Stage Qualification Funnel
// ============================================================================
let currentCategory = 'all';
let currentCompetitor = 'ALL';
let currentViewMode = 'table';
let activeLeadId = null;
let currentPitchTab = 'reply';
let currentSplitPitchTab = 'reply';
let currentSortField = 'default';
let currentSortDir = 'desc';
let customBrandProfile = null;
let lastFocusedTrigger = null;

// Authoritative in-memory session store (initialized once from localStorage; immune to subsequent quota write failures)
const memoryStatusStore = {};
const memoryDisqualifyReasonStore = {};
let sessionStoreInitialized = false;

const QUALIFICATION_STATUSES = [
    '未处理',
    '已核验接受',
    '已触达',
    '有回复',
    '已预约',
    '已成交',
    '不合格'
];

const DISQUALIFY_REASONS = [
    '无替换决策权（如一线员工被动使用）',
    '非目标客群规模（个人/学生项目）',
    '痛点与我方产品能力不匹配',
    '原帖讨论已超期或已完成选型',
    '仅倾诉情绪无迁移预算'
];

const STATUS_CLASSES = {
    '未处理': 'bg-zinc-100 text-zinc-700 border-zinc-200 hover:bg-zinc-200/80',
    '已核验接受': 'bg-blue-50 text-blue-800 border-blue-200 hover:bg-blue-100',
    '已触达': 'bg-indigo-50 text-indigo-800 border-indigo-200 hover:bg-indigo-100',
    '有回复': 'bg-amber-50 text-amber-800 border-amber-300 hover:bg-amber-100',
    '已预约': 'bg-purple-50 text-purple-800 border-purple-200 hover:bg-purple-100',
    '已成交': 'bg-emerald-50 text-emerald-800 border-emerald-300 hover:bg-emerald-100',
    '不合格': 'bg-rose-50 text-rose-800 border-rose-200 hover:bg-rose-100'
};

const PROVENANCE_BADGE_CLASSES = {
    '原文明示': 'bg-emerald-50 text-emerald-800 border-emerald-200',
    '模型推断': 'bg-amber-50 text-amber-800 border-amber-200',
    '未知': 'bg-zinc-100 text-zinc-600 border-zinc-200'
};

function initSessionStateFromStorage() {
    if (sessionStoreInitialized) return;
    sessionStoreInitialized = true;
    if (typeof LEADS_DATA === 'undefined' || !Array.isArray(LEADS_DATA)) return;
    LEADS_DATA.forEach(lead => {
        if (!lead || !lead.id) return;
        try {
            const savedStatus = localStorage.getItem('ir_lead_status_' + lead.id);
            if (savedStatus && QUALIFICATION_STATUSES.includes(savedStatus)) {
                memoryStatusStore[lead.id] = savedStatus;
            }
            const savedDisq = localStorage.getItem('ir_lead_disq_' + lead.id);
            if (savedDisq) {
                memoryDisqualifyReasonStore[lead.id] = savedDisq;
            }
        } catch (e) {}
    });
}

function getLeadStatus(id) {
    initSessionStateFromStorage();
    if (Object.prototype.hasOwnProperty.call(memoryStatusStore, id)) {
        return memoryStatusStore[id];
    }
    try {
        const val = localStorage.getItem('ir_lead_status_' + id);
        if (val && QUALIFICATION_STATUSES.includes(val)) {
            memoryStatusStore[id] = val;
            return val;
        }
    } catch (e) {}
    return '未处理';
}

function getDisqualifyReason(id) {
    initSessionStateFromStorage();
    if (Object.prototype.hasOwnProperty.call(memoryDisqualifyReasonStore, id)) {
        return memoryDisqualifyReasonStore[id];
    }
    try {
        const val = localStorage.getItem('ir_lead_disq_' + id);
        if (val) {
            memoryDisqualifyReasonStore[id] = val;
            return val;
        }
    } catch (e) {}
    return '';
}

function setLeadStatus(id, newStatus, reason = null) {
    if (!QUALIFICATION_STATUSES.includes(newStatus)) return;
    initSessionStateFromStorage();
    // Session memory is ALWAYS updated first and remains authoritative even if localStorage fails
    memoryStatusStore[id] = newStatus;
    if (reason !== null) {
        memoryDisqualifyReasonStore[id] = reason;
    } else if (newStatus === '不合格' && !memoryDisqualifyReasonStore[id]) {
        const lead = (typeof LEADS_DATA !== 'undefined' ? LEADS_DATA : []).find(x => x.id === id);
        const defaultReason = (lead && isAuthorityNegated(lead))
            ? '无替换决策权（如一线员工被动使用）'
            : DISQUALIFY_REASONS[0];
        memoryDisqualifyReasonStore[id] = defaultReason;
    }

    let persistedOk = true;
    try {
        localStorage.setItem('ir_lead_status_' + id, newStatus);
        if (newStatus === '不合格') {
            localStorage.setItem('ir_lead_disq_' + id, memoryDisqualifyReasonStore[id] || DISQUALIFY_REASONS[0]);
        }
    } catch (e) {
        persistedOk = false;
        console.warn('localStorage write failed:', e);
    }

    applyRender();
    if (activeLeadId === id) {
        updateDrawerStatusUI(newStatus, getDisqualifyReason(id));
        updateSplitStatusUI(newStatus, getDisqualifyReason(id));
    }

    if (!persistedOk) {
        showToast(`本地存储受限（localStorage 写入失败），状态【${newStatus}】已在当前会话内存中生效`, true);
    } else {
        const suffix = (newStatus === '不合格' && getDisqualifyReason(id)) ? `（原因：${getDisqualifyReason(id)}）` : '';
        showToast(`已记录线索状态为【${newStatus}】${suffix}`);
    }
}

function cycleStatus(id) {
    const current = getLeadStatus(id);
    const idx = QUALIFICATION_STATUSES.indexOf(current);
    const nextStatus = QUALIFICATION_STATUSES[(idx + 1) % QUALIFICATION_STATUSES.length];
    setLeadStatus(id, nextStatus);
}

// Sync cross-tab storage updates into session memory
window.addEventListener('storage', (e) => {
    if (!e || !e.key) return;
    if (e.key.startsWith('ir_lead_status_')) {
        const id = e.key.replace('ir_lead_status_', '');
        if (e.newValue && QUALIFICATION_STATUSES.includes(e.newValue)) {
            memoryStatusStore[id] = e.newValue;
            applyRender();
        }
    } else if (e.key.startsWith('ir_lead_disq_')) {
        const id = e.key.replace('ir_lead_disq_', '');
        if (e.newValue !== null) {
            memoryDisqualifyReasonStore[id] = e.newValue;
            applyRender();
        }
    }
});

// ============================================================================
// 3. Unified 4-Stage Sequential Qualification & Outreach Policy Engine
// ============================================================================
function isAuthorityNegated(lead) {
    if (!lead) return true;
    const qm = lead.qualification_meta || {};
    const authVal = (qm.decision_authority && qm.decision_authority.value) || '';
    const fullText = ((lead.title || '') + ' ' + (lead.content || '')).toLowerCase();
    return (
        lead.intent_type === 'lack_of_authority' ||
        lead.intent_type === 'negative_no_replacement' ||
        lead.intent_type === 'vendor_self_promotion' ||
        authVal.includes('无采购与替换决策权') ||
        authVal.includes('无选型决定权') ||
        fullText.includes('not my choice')
    );
}

function hasReplacementAuthority(lead) {
    if (!lead || isAuthorityNegated(lead)) return false;
    const qm = lead.qualification_meta || {};
    const authSrc = (qm.decision_authority && (qm.decision_authority.source || qm.decision_authority.provenance)) || '未知';
    // CRITICAL (Audit Finding #6): "未知" authority is NEVER treated as verified replacement authority!
    return authSrc === '原文明示' || authSrc === '模型推断';
}

function checkBrandCompatibility(lead, profile) {
    if (!profile || !profile.brand_name) {
        return { compatible: false, mode: 'unconfigured', reason: '当前未配置特定卖方产品能力档案（阶段 3 待核验）' };
    }
    const cleanTargets = (profile.target_competitors || []).map(t => String(t).trim()).filter(t => t && t !== '*');
    const approvedCaps = String(profile.approved_capabilities || '').trim();
    if (cleanTargets.length === 0 || !approvedCaps) {
        return {
            compatible: false,
            mode: 'incomplete_profile',
            reason: `卖方档案【${profile.brand_name}】缺少明确的「适配被替换竞品」或「已核准真实能力」（系统禁止默认使用 * 通配符或自动补造能力）。`
        };
    }
    const leadCompLower = (lead.competitor || '').toLowerCase();
    const isMatch = cleanTargets.some(t => {
        const tl = t.toLowerCase();
        return leadCompLower.includes(tl) || tl.includes(leadCompLower);
    });
    if (!isMatch) {
        return {
            compatible: false,
            mode: 'mismatch',
            reason: `当前已选卖方产品为【${profile.brand_name}】（仅适配替换：${cleanTargets.join(' / ')}），而本条线索被替换标的为【${lead.competitor}】（${lead.category}）。跨赛道强行套用话术已被系统拦截。`
        };
    }
    return { compatible: true, mode: 'matched', reason: `卖方【${profile.brand_name}】赛道与核准能力已匹配` };
}

function evaluateLeadStages(lead, profile) {
    const qm = lead.qualification_meta || {};
    const authSrc = (qm.decision_authority && (qm.decision_authority.source || qm.decision_authority.provenance)) || '未知';
    const budgetSrc = (qm.budget_status && (qm.budget_status.source || qm.budget_status.provenance)) || '未知';
    const negated = isAuthorityNegated(lead);

    const s1Passed = lead.intent_type !== 'vendor_self_promotion' && lead.competitor && lead.competitor !== '未知';
    const s2Passed = s1Passed && !negated;

    let s3Passed = false;
    let s3Status = '待核验 · 未配置特定卖方能力档案';
    let s3Blocker = '客户能力未知时不能通过阶段 3；请先在上方选择或填写卖方能力档案';
    const compat = checkBrandCompatibility(lead, profile);
    if (!s2Passed) {
        s3Status = '未通过 · 前置阶段未成立';
        s3Blocker = '发帖人无替换决策权或明确不考虑替换';
    } else if (profile && profile.brand_name) {
        if (compat.compatible) {
            s3Passed = true;
            s3Status = `已通过 · 适配【${profile.brand_name}】`;
            s3Blocker = profile.known_limitations || '';
        } else {
            s3Passed = false;
            s3Status = compat.mode === 'incomplete_profile' ? '受阻 · 卖方档案不完整' : '已拦截 · 跨赛道能力不匹配';
            s3Blocker = compat.reason;
        }
    }

    const bothUnknown = (authSrc === '未知' && budgetSrc === '未知');
    const isSparse = ((lead.content || '').trim().length < 100 && bothUnknown);
    let s4Passed = false;
    let s4Status = '待推进';
    if (s3Passed && !isSparse && lead.delivery_eligible) {
        s4Passed = true;
        s4Status = '已通过 · 当期可推进商机';
    } else if (s3Passed && isSparse) {
        s4Status = '待核验 · 预算与权限未知（仅可提问）';
    } else if (s3Passed && !lead.delivery_eligible) {
        s4Status = '历史基准样本 · 仅供核验演练（不计当期交付）';
    }

    let contiguous = 0;
    for (const p of [s1Passed, s2Passed, s3Passed, s4Passed]) {
        if (p) contiguous += 1;
        else break;
    }

    let stageLabel = lead.qualification_stage || '阶段 2/4 · 正在评估替代';
    if (contiguous === 0) {
        stageLabel = '阶段 0/4 · 非买方替换线索';
    } else if (contiguous === 1) {
        stageLabel = '阶段 1/4 · 仅抱怨竞品（无替换决策权）';
    } else if (contiguous === 2) {
        if (profile && profile.brand_name && !compat.compatible) {
            stageLabel = `阶段 2/4 · 阶段3受阻（${compat.mode === 'mismatch' ? '跨赛道不匹配' : '档案不完整'}）`;
        } else if (bothUnknown) {
            stageLabel = '阶段 2/4 · 初步寻优（预算/权限与卖方适配待核验）';
        } else {
            stageLabel = '阶段 2/4 · 正在评估替代（待绑定卖方能力核验阶段3）';
        }
    } else if (contiguous === 3) {
        if (bothUnknown) {
            stageLabel = '阶段 3/4 · 卖方能力已匹配（预算/权限未知·先提问核实）';
        } else if (!lead.delivery_eligible) {
            stageLabel = '阶段 3/4 · 卖方能力已匹配（历史基准样本·不计当期交付）';
        } else {
            stageLabel = '阶段 3/4 · 卖方能力已匹配（待首轮确认）';
        }
    } else {
        stageLabel = '阶段 4/4 · 四步核验全部通过（当期可推进商机）';
    }

    return {
        contiguous,
        stageLabel,
        s1Passed,
        s2Passed,
        s3Passed,
        s4Passed,
        s3Status,
        s3Blocker,
        s4Status,
        compat,
        bothUnknown
    };
}

function getEffectivePitch(lead, type = 'reply') {
    if (!lead) return '';
    const st = evaluateLeadStages(lead, customBrandProfile);

    // 1. Blocked if Stage 1 or Stage 2 failed (lack of authority / negative intent / vendor post)
    if (!st.s2Passed) {
        if (lead.outreach_policy && lead.outreach_policy.policy_status === 'blocked' && lead.public_reply) {
            return lead.public_reply;
        }
        const quote = lead.evidence_quote || lead.content || '';
        return `⚠️ 【资格核验拦截 · 已禁止发送推销话术】\n` +
               `原因：原帖作者 @${lead.author} 在正文中明确表示 "${quote}"（无工具选型与替换决策权）。\n` +
               `处置要求：将该帖标记为「不合格（原因：无替换决策权）」，仅保留痛点作为产品研发参考，严禁外呼打扰。`;
    }

    // 2. If no custom brand is active, return backend's strictly neutral qualification questions (zero capability claims)
    if (!customBrandProfile || !customBrandProfile.brand_name) {
        if (type === 'dev') return lead.pitch_dev || lead.suggested_pitch || '';
        if (type === 'exec') return lead.pitch_exec || lead.suggested_pitch || '';
        return lead.public_reply || '';
    }

    // 3. If custom brand is active, check Stage 3 compatibility & profile completeness
    if (!st.s3Passed) {
        return `⛔ 【卖方能力门控拦截 · 已禁止生成推荐话术】\n${st.compat.reason}\n💡 解决方案：请在上方「卖方产品能力档案」中切换至适配【${lead.competitor}】且包含完整核准能力的预设，或切回「默认中立核验视角」。`;
    }

    const bName = customBrandProfile.brand_name;
    const actorRole = customBrandProfile.actor_role || '产品团队成员';
    const bCaps = customBrandProfile.approved_capabilities;
    const bLimits = customBrandProfile.known_limitations || '具体生产环境兼容性仍需根据贵司实际架构核实';
    const bLink = customBrandProfile.cta_link || '';
    const evidenceSnippet = (lead.evidence_quote || lead.title || '').slice(0, 120);
    const blockers = (lead.qualification_meta && lead.qualification_meta.blocking_conditions && lead.qualification_meta.blocking_conditions.length > 0)
        ? lead.qualification_meta.blocking_conditions.join('；')
        : '具体席位规模与现有历史数据迁移边界待确认';

    const disclosure = `利益相关披露：我是【${bName}】的${actorRole}。`;

    // 4. If budget & authority are both unknown (e.g., 1-sentence inquiry), only allow neutral qualification question with disclosure
    if (st.bothUnknown) {
        return `${disclosure}\n` +
               `看到你在寻找 ${lead.competitor} 的替代方案（“${evidenceSnippet}”）。\n` +
               `由于原帖尚未披露具体使用模块、团队席位数与预算形式（开源自托管或商业托管），方便补充一下你们最核心的 1-2 个必选需求吗？\n` +
               `我们可以据此客观核对是否属于【${bName}】的已核准支持范围（已知边界：${bLimits}）。`;
    }

    // 5. Stage 3 passed & authority/budget not blank -> Approved Recommendation with role-accurate disclosure
    if (type === 'reply') {
        return `${disclosure}\n` +
               `针对你在原帖提到的「${evidenceSnippet}」，【${bName}】目前已核准支持的能力包括：${bCaps}。\n` +
               `但需要客观说明已知边界：【${bLimits}】；同时原帖尚未涉及【${blockers}】，仍需结合你们的具体场景确认。\n` +
               `${bLink ? '这里有对应的迁移核验文档：' + bLink + ' ，' : ''}建议先用一小份脱敏数据做最小化验证。`;
    } else if (type === 'dev') {
        return `Hi @${lead.author}，在 ${lead.source} 看到你关于 ${lead.competitor} 的讨论（原帖提及：“${evidenceSnippet}”）。\n` +
               `${disclosure}针对该场景，我们已核准支持：${bCaps}。\n` +
               `在判断是否适合你们团队前，想先请教并确认两个边界问题：1) ${bLimits}；2) ${blockers}。\n` +
               `${bLink ? '迁移验证指南参考：' + bLink : '方便的话可以先跑一下沙箱导入测试。'}`;
    } else {
        return `您好 @${lead.author}，关注到贵团队在 ${lead.source} 评估 ${lead.competitor} 的替代方案。\n` +
               `${disclosure}对照原帖提到的痛点，我方已核准支持：${bCaps}。\n` +
               `目前尚待确认的阻碍条件包括：【${blockers}】以及【${bLimits}】。建议先安排 15 分钟技术边界核对或小样本导入测试，确认完全匹配后再评估商务方案。`;
    }
}

// ============================================================================
// 4. Unified Filtering & Sorting Predicates
// ============================================================================
function isHighIntentLead(item) {
    const st = evaluateLeadStages(item, customBrandProfile);
    if (customBrandProfile && customBrandProfile.brand_name) {
        return st.contiguous >= 3 && hasReplacementAuthority(item);
    }
    return st.contiguous >= 2 && item.intent_score >= 80 && hasReplacementAuthority(item);
}

function isCautionOrPendingLead(item) {
    return !isHighIntentLead(item);
}

function isPricingDriverLead(item) {
    const text = ((item.churn_drivers || []).join(' ') + ' ' + item.title + ' ' + (item.evidence_quote || '')).toLowerCase();
    return /价格|成本|费用|涨价|贵|配额|限流|账单|expensive|pricing|rate limit|pro plan/.test(text);
}

function isPrivacyDriverLead(item) {
    const text = ((item.churn_drivers || []).join(' ') + ' ' + item.title + ' ' + (item.evidence_quote || '')).toLowerCase();
    return /隐私|开源|自托管|合规|数据|上云|离线|cloud|offline|scratchpad|self-host|open source/.test(text);
}

function getFilteredLeads() {
    const searchEl = document.getElementById('searchInput');
    const rawQuery = (searchEl ? searchEl.value : '').trim().toLowerCase();
    const tokens = rawQuery.split(/\s+/).filter(Boolean);

    return LEADS_DATA.filter(item => {
        let matchCat = true;
        if (currentCategory === 'high-intent') {
            matchCat = isHighIntentLead(item);
        } else if (currentCategory === 'caution') {
            matchCat = isCautionOrPendingLead(item);
        } else if (currentCategory === 'pricing') {
            matchCat = isPricingDriverLead(item);
        } else if (currentCategory === 'privacy') {
            matchCat = isPrivacyDriverLead(item);
        }

        let matchComp = (currentCompetitor === 'ALL') || (item.competitor.toLowerCase() === currentCompetitor.toLowerCase());

        let matchQuery = true;
        if (tokens.length > 0) {
            const fullText = [
                item.title,
                item.competitor,
                (item.candidate_alternatives || []).join(' '),
                (item.system_recommended_alternatives || []).join(' '),
                item.category,
                item.author,
                item.source_id,
                item.evidence_quote,
                (item.churn_drivers || []).join(' '),
                item.executive_summary || ''
            ].join(' ').toLowerCase();
            matchQuery = tokens.every(t => fullText.includes(t));
        }

        return matchCat && matchComp && matchQuery;
    });
}

function getFilteredAndSortedLeads() {
    const list = getFilteredLeads();
    if (currentSortField === 'score') {
        return [...list].sort((a, b) => currentSortDir === 'asc' ? a.intent_score - b.intent_score : b.intent_score - a.intent_score);
    } else if (currentSortField === 'idx') {
        return [...list].sort((a, b) => currentSortDir === 'asc' ? a.idx - b.idx : b.idx - a.idx);
    }
    return list;
}

// ============================================================================
// 5. Pure-JS Genuine OpenXML (.xlsx) Generator + Explicit Export Controls
// ============================================================================
const CRC32_TABLE = (() => {
    const table = new Uint32Array(256);
    for (let i = 0; i < 256; i++) {
        let c = i;
        for (let k = 0; k < 8; k++) {
            c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1);
        }
        table[i] = c >>> 0;
    }
    return table;
})();

function crc32Bytes(uint8Arr) {
    let crc = 0xFFFFFFFF;
    for (let i = 0; i < uint8Arr.length; i++) {
        crc = CRC32_TABLE[(crc ^ uint8Arr[i]) & 0xFF] ^ (crc >>> 8);
    }
    return (crc ^ 0xFFFFFFFF) >>> 0;
}

function createZipStoreArchive(files) {
    const encoder = new TextEncoder();
    const localParts = [];
    const centralParts = [];
    let offset = 0;

    files.forEach(file => {
        const nameBytes = encoder.encode(file.name);
        const dataBytes = (file.data instanceof Uint8Array) ? file.data : encoder.encode(file.data);
        const crc = crc32Bytes(dataBytes);
        const size = dataBytes.length;

        const localHeader = new Uint8Array(30 + nameBytes.length);
        const lv = new DataView(localHeader.buffer);
        lv.setUint32(0, 0x04034b50, true);
        lv.setUint16(4, 20, true);
        lv.setUint16(6, 0x0800, true);
        lv.setUint16(8, 0, true);
        lv.setUint16(10, 0, true);
        lv.setUint16(12, 0x21, true);
        lv.setUint32(14, crc, true);
        lv.setUint32(18, size, true);
        lv.setUint32(22, size, true);
        lv.setUint16(26, nameBytes.length, true);
        lv.setUint16(28, 0, true);
        localHeader.set(nameBytes, 30);

        const centralHeader = new Uint8Array(46 + nameBytes.length);
        const cv = new DataView(centralHeader.buffer);
        cv.setUint32(0, 0x02014b50, true);
        cv.setUint16(4, 20, true);
        cv.setUint16(6, 20, true);
        cv.setUint16(8, 0x0800, true);
        cv.setUint16(10, 0, true);
        cv.setUint16(12, 0, true);
        cv.setUint16(14, 0x21, true);
        cv.setUint32(16, crc, true);
        cv.setUint32(20, size, true);
        cv.setUint32(24, size, true);
        cv.setUint16(28, nameBytes.length, true);
        cv.setUint16(30, 0, true);
        cv.setUint16(32, 0, true);
        cv.setUint16(34, 0, true);
        cv.setUint16(36, 0, true);
        cv.setUint32(38, 0, true);
        cv.setUint32(42, offset, true);
        centralHeader.set(nameBytes, 46);

        localParts.push(localHeader, dataBytes);
        centralParts.push(centralHeader);
        offset += localHeader.length + size;
    });

    const centralSize = centralParts.reduce((acc, p) => acc + p.length, 0);
    const eocd = new Uint8Array(22);
    const ev = new DataView(eocd.buffer);
    ev.setUint32(0, 0x06054b50, true);
    ev.setUint16(4, 0, true);
    ev.setUint16(6, 0, true);
    ev.setUint16(8, files.length, true);
    ev.setUint16(10, files.length, true);
    ev.setUint32(12, centralSize, true);
    ev.setUint32(16, offset, true);
    ev.setUint16(20, 0, true);

    return new Blob([...localParts, ...centralParts, eocd], {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    });
}

function excelColName(colIdxZeroBased) {
    let n = colIdxZeroBased + 1;
    let s = '';
    while (n > 0) {
        const m = (n - 1) % 26;
        s = String.fromCharCode(65 + m) + s;
        n = Math.floor((n - 1) / 26);
    }
    return s;
}

function escapeXmlText(val) {
    if (val === null || val === undefined) return '';
    const cleaned = String(val).replace(/[\x00-\x08\x0B\x0C\x0E-\x1F]/g, '');
    return cleaned
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&apos;');
}

function buildRealXlsxBlob(headers, rows, colWidths) {
    const lastColLetter = excelColName(headers.length - 1);
    const totalRows = rows.length + 1;

    const colsXml = colWidths.map((w, i) =>
        `<col min="${i + 1}" max="${i + 1}" width="${w}" customWidth="1"/>`
    ).join('');

    const headerCellsXml = headers.map((h, cIdx) => {
        const ref = `${excelColName(cIdx)}1`;
        const safeText = escapeXmlText(normalizeXlsxCellText(h));
        return `<c r="${ref}" s="1" t="inlineStr"><is><t xml:space="preserve">${safeText}</t></is></c>`;
    }).join('');

    const dataRowsXml = rows.map((row, rIdx) => {
        const rowNum = rIdx + 2;
        const cellsXml = row.map((cellVal, cIdx) => {
            const ref = `${excelColName(cIdx)}${rowNum}`;
            const safeText = escapeXmlText(normalizeXlsxCellText(cellVal));
            return `<c r="${ref}" s="2" t="inlineStr"><is><t xml:space="preserve">${safeText}</t></is></c>`;
        }).join('');
        return `<row r="${rowNum}">${cellsXml}</row>`;
    }).join('');

    const sheetXml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetViews>
    <sheetView tabSelected="1" workbookViewId="0">
      <pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>
    </sheetView>
  </sheetViews>
  <cols>${colsXml}</cols>
  <sheetData>
    <row r="1" ht="24" customHeight="1">${headerCellsXml}</row>
    ${dataRowsXml}
  </sheetData>
  <autoFilter ref="A1:${lastColLetter}${totalRows}"/>
</worksheet>`;

    const stylesXml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="2">
    <font><sz val="10"/><color rgb="FF18181B"/><name val="Calibri"/></font>
    <font><b/><sz val="10"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font>
  </fonts>
  <fills count="3">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF18181B"/></patternFill></fill>
  </fills>
  <borders count="2">
    <border><left/><right/><top/><bottom/><diagonal/></border>
    <border>
      <left style="thin"><color rgb="FFE4E4E7"/></left>
      <right style="thin"><color rgb="FFE4E4E7"/></right>
      <top style="thin"><color rgb="FFE4E4E7"/></top>
      <bottom style="thin"><color rgb="FFE4E4E7"/></bottom>
      <diagonal/>
    </border>
  </borders>
  <cellStyleXfs count="1">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0"/>
  </cellStyleXfs>
  <cellXfs count="3">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
    <xf numFmtId="49" fontId="1" fillId="2" borderId="1" xfId="0" applyNumberFormat="1" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1">
      <alignment horizontal="left" vertical="center" wrapText="1"/>
    </xf>
    <xf numFmtId="49" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyFont="1" applyBorder="1" applyAlignment="1">
      <alignment horizontal="left" vertical="top" wrapText="1"/>
    </xf>
  </cellXfs>
  <cellStyles count="1">
    <cellStyle name="Normal" xfId="0" builtinId="0"/>
  </cellStyles>
</styleSheet>`;

    const workbookXml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="IntentRadar核验台账" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>`;

    const workbookRelsXml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>`;

    const rootRelsXml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>`;

    const contentTypesXml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>`;

    return createZipStoreArchive([
        { name: '[Content_Types].xml', data: contentTypesXml },
        { name: '_rels/.rels', data: rootRelsXml },
        { name: 'xl/workbook.xml', data: workbookXml },
        { name: 'xl/_rels/workbook.xml.rels', data: workbookRelsXml },
        { name: 'xl/styles.xml', data: stylesXml },
        { name: 'xl/worksheets/sheet1.xml', data: sheetXml }
    ]);
}

function buildExportTableData(leads) {
    const headers = [
        '序号', '来源平台', '来源原帖ID', '发布时间(UTC)', '采集核验时间(UTC)',
        '四步资格核验阶段', '意向评分', '被替换竞品(Incumbent)', '原文提及候选(系统推荐另列)',
        '原帖标题', '原文关键证据摘录', '发帖人账号',
        '团队规模及来源', '预算状态及来源', '决策权限及来源', '迁移急迫度及来源',
        '待核验阻碍条件', '建议触达路径', '跟进状态', '不合格原因',
        '公开沟通草稿(受门控约束)', '1v1技术核验草稿', '商业可行性核验草稿', '原帖直达链接'
    ];
    const colWidths = [
        6, 14, 14, 18, 18,
        28, 10, 18, 28,
        34, 42, 16,
        24, 24, 26, 24,
        36, 30, 12, 22,
        42, 42, 42, 36
    ];

    const formatMetaField = (metaObj) => {
        if (!metaObj) return '[未知] 未披露';
        return `[${metaObj.source || '未知'}] ${metaObj.value || '未披露'}`;
    };

    const rows = leads.map(l => {
        const qm = l.qualification_meta || {};
        const st = evaluateLeadStages(l, customBrandProfile);
        const authorCands = (l.candidate_alternatives && l.candidate_alternatives.length > 0)
            ? `原文提及:${l.candidate_alternatives.join(',')}`
            : '原文未提及候选';
        const sysCands = (l.system_recommended_alternatives && l.system_recommended_alternatives.length > 0)
            ? ` | 系统推荐:${l.system_recommended_alternatives.join(',')}`
            : '';
        return [
            String(l.idx),
            l.source || '',
            l.source_id || l.id || '',
            l.timestamp || '',
            l.collected_at || '',
            st.stageLabel,
            `${l.intent_score}分`,
            l.competitor || '',
            authorCands + sysCands,
            l.title || '',
            l.evidence_quote || l.content || '',
            l.author || '',
            formatMetaField(qm.team_scale),
            formatMetaField(qm.budget_status),
            formatMetaField(qm.decision_authority),
            formatMetaField(qm.migration_urgency),
            (qm.blocking_conditions || []).join('；'),
            qm.contact_path || '',
            getLeadStatus(l.id),
            getLeadStatus(l.id) === '不合格' ? getDisqualifyReason(l.id) : '',
            getEffectivePitch(l, 'reply'),
            getEffectivePitch(l, 'dev'),
            getEffectivePitch(l, 'exec'),
            l.url || ''
        ];
    });

    return { headers, rows, colWidths };
}

function triggerExport(scope = 'filtered', format = 'xlsx') {
    const leads = (scope === 'all') ? LEADS_DATA : getFilteredAndSortedLeads();
    if (!leads || leads.length === 0) {
        showToast('当前筛选结果为 0 条，无法导出。请调整筛选条件或点击「导出全库」。', true);
        return;
    }

    const { headers, rows, colWidths } = buildExportTableData(leads);
    const scopeLabel = (scope === 'all') ? `全库_${leads.length}条` : `当前筛选_${leads.length}条`;
    const dateStr = new Date().toISOString().slice(0, 10);

    if (format === 'xlsx') {
        const blob = buildRealXlsxBlob(headers, rows, colWidths);
        const link = document.createElement('a');
        const url = URL.createObjectURL(blob);
        link.setAttribute('href', url);
        link.setAttribute('download', `IntentRadar_核验台账_${scopeLabel}_${dateStr}.xlsx`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        setTimeout(() => URL.revokeObjectURL(url), 1500);
        showToast(`已导出真实 .xlsx 核验台账（${scope === 'all' ? '全库' : '当前筛选'} ${leads.length} 条，含 Normal 样式与冻结首行）`);
    } else {
        const cleanCsvCell = (val) => {
            const safeVal = sanitizeCsvCell(val);
            return `"${String(safeVal).replace(/"/g, '""').replace(/[\r\n]+/g, ' ')}"`;
        };
        const csvLines = [
            headers.map(cleanCsvCell).join(','),
            ...rows.map(r => r.map(cleanCsvCell).join(','))
        ];
        const blob = new Blob(['\uFEFF' + csvLines.join('\n')], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        const url = URL.createObjectURL(blob);
        link.setAttribute('href', url);
        link.setAttribute('download', `IntentRadar_核验台账_${scopeLabel}_${dateStr}.csv`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        setTimeout(() => URL.revokeObjectURL(url), 1500);
        showToast(`已导出 CSV 核验台账（${scope === 'all' ? '全库' : '当前筛选'} ${leads.length} 条，已启用 OWASP 公式防注入）`);
    }
}

function copyFilteredPitches(btn) {
    const leads = getFilteredAndSortedLeads();
    if (!leads || leads.length === 0) {
        showToast('当前筛选结果为 0 条，没有可复制的话术', true);
        return;
    }
    const eligibleLeads = leads.filter(l => {
        const st = evaluateLeadStages(l, customBrandProfile);
        if (!st.s2Passed) return false;
        if (customBrandProfile && customBrandProfile.brand_name && !st.s3Passed) return false;
        return true;
    });
    if (eligibleLeads.length === 0) {
        showToast('当前筛选线索均因「跨赛道不匹配」「档案不完整」或「无选型决策权」被拦截', true);
        return;
    }
    const skippedCount = leads.length - eligibleLeads.length;
    const fullText = eligibleLeads.map(l =>
        `【#${l.idx} 标的：${l.competitor} | 发帖人：@${l.author} | 来源ID：${l.source_id}】\n` +
        `原帖链接：${l.url}\n` +
        `原文证据：“${l.evidence_quote}”\n` +
        `【💬 公开沟通草稿】：\n${getEffectivePitch(l, 'reply')}\n` +
        `【💻 1v1 核验草稿】：\n${getEffectivePitch(l, 'dev')}`
    ).join('\n\n========================================\n\n');

    const msg = skippedCount > 0
        ? `已复制 ${eligibleLeads.length} 条合规草稿（自动拦截跳过 ${skippedCount} 条无决策权或不匹配线索）`
        : `已复制当前筛选 ${eligibleLeads.length} 条合规沟通草稿！`;
    copyToClipboard(fullText, msg, btn);
}
"""

CLIENT_WORKBENCH_UI_JS = r"""
// ============================================================================
// 6. UI Rendering, Provenance Badges, Accessibility & Event Delegation
// ============================================================================
function getBrandLogoHtml(name, size = 'w-3.5 h-3.5') {
    const raw = (name || '').toLowerCase().trim();
    const firstPart = raw.split('/')[0].trim();
    const iconUri = BRAND_ICONS[raw] || BRAND_ICONS[firstPart];
    if (iconUri) {
        return `<img src="${escapeHtml(iconUri)}" class="${size} inline-block object-contain flex-shrink-0 rounded-[3px]" alt="${escapeHtml(name)}" loading="lazy" />`;
    }
    return `<span class="inline-flex items-center justify-center ${size} rounded-[3px] bg-zinc-700 text-white text-[9px] font-bold flex-shrink-0">${escapeHtml((name || 'IR').slice(0, 2).toUpperCase())}</span>`;
}

function renderProvenanceBadge(metaItem, label) {
    const src = (metaItem && metaItem.source) ? metaItem.source : '未知';
    const val = (metaItem && metaItem.value) ? metaItem.value : '未披露';
    const ev = (metaItem && metaItem.evidence) ? metaItem.evidence : '';
    const cls = PROVENANCE_BADGE_CLASSES[src] || PROVENANCE_BADGE_CLASSES['未知'];
    return `
    <div class="p-2.5 rounded-lg bg-zinc-50/90 border border-zinc-200/80 flex flex-col justify-between gap-1">
        <div class="flex items-center justify-between gap-1">
            <span class="text-[11px] font-semibold text-zinc-500">${escapeHtml(label)}</span>
            <span class="px-1.5 py-0.2 rounded text-[10px] font-bold border ${cls}">[${escapeHtml(src)}]</span>
        </div>
        <div class="text-xs font-medium text-zinc-800 leading-snug">${escapeHtml(val)}</div>
        ${ev ? `<div class="text-[10px] text-zinc-500 italic line-clamp-1" title="原文依据：${escapeHtml(ev)}">依据: "${escapeHtml(ev)}"</div>` : ''}
    </div>`;
}

function getScoreBadgeHtml(lead) {
    const st = evaluateLeadStages(lead, customBrandProfile);
    if (!st.s2Passed) {
        return `<span class="whitespace-nowrap inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-50 text-amber-800 border border-amber-300" title="阶段 1/4：发帖人明示无选型决策权或已拦截"><span class="w-1.5 h-1.5 rounded-full bg-amber-500"></span>${lead.intent_score}分 · 阶段 ${st.contiguous}/4</span>`;
    }
    if (st.contiguous >= 3) {
        return `<span class="whitespace-nowrap inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200"><span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>${lead.intent_score}分 · 阶段 ${st.contiguous}/4</span>`;
    }
    if (hasReplacementAuthority(lead) && lead.intent_score >= 80) {
        return `<span class="whitespace-nowrap inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-blue-50 text-blue-800 border border-blue-200" title="阶段 2/4 已通过，待配置卖方能力档案验证阶段 3"><span class="w-1.5 h-1.5 rounded-full bg-blue-500"></span>${lead.intent_score}分 · 阶段 ${st.contiguous}/4</span>`;
    }
    return `<span class="whitespace-nowrap inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-zinc-100 text-zinc-700 border border-zinc-300"><span class="w-1.5 h-1.5 rounded-full bg-zinc-500"></span>${lead.intent_score}分 · 阶段 ${st.contiguous}/4</span>`;
}

function updateLiveCountsAndExportButtons(filteredLeads) {
    const total = LEADS_DATA.length;
    const count = filteredLeads.length;

    const liveCounterEl = document.getElementById('liveFilterSummary');
    if (liveCounterEl) {
        const activeLead = LEADS_DATA.find(l => l.id === activeLeadId);
        const selText = activeLead ? ` · 当前选中 #${activeLead.idx} (${activeLead.competitor})` : '';
        liveCounterEl.innerText = `当前筛选显示 ${count} / ${total} 条样本${selText}`;
    }

    const btnExpFilteredXlsx = document.getElementById('btnExportFilteredXlsx');
    const btnExpFilteredCsv = document.getElementById('btnExportFilteredCsv');
    const btnExpAllXlsx = document.getElementById('btnExportAllXlsx');
    const btnCopyFiltered = document.getElementById('btnCopyFilteredPitches');

    if (btnExpFilteredXlsx) {
        btnExpFilteredXlsx.innerHTML = `<svg class="w-3.5 h-3.5 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg><span>导出当前筛选 (${count}条 .xlsx)</span>`;
        btnExpFilteredXlsx.disabled = (count === 0);
        btnExpFilteredXlsx.className = (count === 0)
            ? 'inline-flex items-center px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-zinc-200 text-zinc-400 cursor-not-allowed whitespace-nowrap'
            : 'inline-flex items-center px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-emerald-600 hover:bg-emerald-700 text-white shadow-xs transition-colors whitespace-nowrap';
    }
    if (btnExpFilteredCsv) {
        btnExpFilteredCsv.innerText = `导出当前 CSV (${count}条)`;
        btnExpFilteredCsv.disabled = (count === 0);
        btnExpFilteredCsv.className = (count === 0)
            ? 'inline-flex items-center px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-zinc-100 text-zinc-400 border border-zinc-200 cursor-not-allowed whitespace-nowrap'
            : 'inline-flex items-center px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-white hover:bg-zinc-100 text-zinc-800 border border-zinc-300 shadow-2xs transition-colors whitespace-nowrap';
    }
    if (btnExpAllXlsx) {
        btnExpAllXlsx.innerText = `导出全库 (${total}条 .xlsx)`;
        btnExpAllXlsx.disabled = (total === 0);
    }
    if (btnCopyFiltered) {
        btnCopyFiltered.disabled = (count === 0);
    }
}

function renderTable(leads) {
    const tbody = document.getElementById('leadTableBody');
    const emptyState = document.getElementById('empty-state');
    const tableWrapper = document.getElementById('tableViewWrapper');
    if (!tbody || !tableWrapper) return;

    if (leads.length === 0) {
        tbody.innerHTML = '';
        tableWrapper.classList.add('hidden');
        emptyState.classList.remove('hidden');
        return;
    }

    emptyState.classList.add('hidden');
    tableWrapper.classList.remove('hidden');

    tbody.innerHTML = leads.map((lead) => {
        const status = getLeadStatus(lead.id);
        const disqReason = getDisqualifyReason(lead.id);
        const statusClass = STATUS_CLASSES[status] || STATUS_CLASSES['未处理'];
        const logoHtml = getBrandLogoHtml(lead.competitor);
        const qm = lead.qualification_meta || {};
        const scaleSrc = (qm.team_scale && qm.team_scale.source) || '未知';
        const budgetSrc = (qm.budget_status && qm.budget_status.source) || '未知';
        const authSrc = (qm.decision_authority && qm.decision_authority.source) || '未知';
        const blockerText = (qm.blocking_conditions && qm.blocking_conditions[0]) || '待核验具体迁移边界';
        const st = evaluateLeadStages(lead, customBrandProfile);

        let compatBadge = '';
        if (customBrandProfile && customBrandProfile.brand_name) {
            if (!st.s3Passed) {
                compatBadge = `<span class="whitespace-nowrap flex-shrink-0 inline-flex items-center px-1.5 py-0.2 rounded text-[10px] font-semibold bg-rose-50 text-rose-700 border border-rose-200">⛔ ${st.compat.mode === 'incomplete_profile' ? '档案不完整' : '跨赛道不匹配'}</span>`;
            } else {
                compatBadge = `<span class="whitespace-nowrap flex-shrink-0 inline-flex items-center px-1.5 py-0.2 rounded text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">✅ 阶段3适配 ${escapeHtml(customBrandProfile.brand_name)}</span>`;
            }
        }

        const candText = (lead.candidate_alternatives && lead.candidate_alternatives.length > 0)
            ? `原文提及候选: ${lead.candidate_alternatives.join(', ')}`
            : `原文未提及候选${lead.system_recommended_alternatives && lead.system_recommended_alternatives.length ? ' (系统推荐: ' + lead.system_recommended_alternatives.slice(0, 2).join('/') + ')' : ''}`;

        const isActive = (lead.id === activeLeadId);
        const rowClasses = isActive
            ? 'bg-emerald-50/70 ring-1 ring-emerald-500/40 transition-colors group cursor-pointer'
            : 'hover:bg-zinc-50/90 transition-colors group cursor-pointer';

        const safeUrl = escapeHtml(sanitizeUrl(lead.url));

        return `
        <tr class="${rowClasses}" data-action="open-drawer" data-lead-id="${escapeHtml(lead.id)}">
            <td class="py-2.5 px-2 font-mono text-zinc-400 text-center text-[11px]">${lead.idx}</td>
            <td class="py-2.5 px-2 whitespace-nowrap">
                <div class="flex flex-col gap-1 items-start">
                    ${getScoreBadgeHtml(lead)}
                    <span class="text-[10px] text-zinc-500 font-medium">${escapeHtml(st.stageLabel.split('·')[1] || st.stageLabel)}</span>
                </div>
            </td>
            <td class="py-2.5 px-2 whitespace-nowrap">
                <div class="flex flex-col gap-1 items-start">
                    <span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs font-semibold bg-zinc-100 text-zinc-800 border border-zinc-200/80">
                        ${logoHtml}
                        <span>${escapeHtml(lead.competitor)}</span>
                    </span>
                    <span class="text-[10px] text-zinc-500 truncate max-w-[165px]" title="${escapeHtml(candText)}">${escapeHtml(candText)}</span>
                </div>
            </td>
            <td class="py-2.5 px-2.5 max-w-[430px]">
                <div class="flex items-center gap-1.5 mb-0.5">
                    <span class="font-semibold text-zinc-900 group-hover:text-emerald-700 transition-colors line-clamp-1 leading-snug">${escapeHtml(lead.title)}</span>
                    ${compatBadge}
                </div>
                <div class="text-[11px] text-zinc-600 italic bg-zinc-50 px-2 py-1 rounded border border-zinc-200/70 line-clamp-1 mb-1" title="${escapeHtml(lead.evidence_quote)}">
                    证据：“${escapeHtml(lead.evidence_quote)}”
                </div>
                <div class="flex items-center flex-wrap gap-1 text-[10px]">
                    <span class="px-1.5 py-0.2 rounded border ${PROVENANCE_BADGE_CLASSES[scaleSrc]}">规模:${escapeHtml(scaleSrc)}</span>
                    <span class="px-1.5 py-0.2 rounded border ${PROVENANCE_BADGE_CLASSES[budgetSrc]}">预算:${escapeHtml(budgetSrc)}</span>
                    <span class="px-1.5 py-0.2 rounded border ${PROVENANCE_BADGE_CLASSES[authSrc]}">决策权:${escapeHtml(authSrc)}</span>
                    <span class="text-zinc-400 truncate max-w-[210px]" title="待核验阻碍：${escapeHtml(blockerText)}">· 阻碍：${escapeHtml(blockerText)}</span>
                </div>
            </td>
            <td class="py-2.5 px-2 whitespace-nowrap">
                <div class="text-[11px] font-mono text-zinc-800">发布: ${escapeHtml(lead.timestamp)}</div>
                <div class="text-[10px] font-mono text-zinc-400">核验: ${escapeHtml(lead.collected_at)}</div>
                <div class="text-[10px] text-amber-700 font-medium mt-0.5">${escapeHtml(lead.source)} #${escapeHtml(lead.source_id)} · ${escapeHtml(lead.engagement)}</div>
            </td>
            <td class="py-2.5 px-2 whitespace-nowrap" data-stop-propagation="true">
                <div class="flex flex-col gap-1 items-start">
                    <button type="button" data-action="cycle-status" data-lead-id="${escapeHtml(lead.id)}" class="px-2 py-0.5 rounded-md text-[11px] font-semibold border transition-all ${statusClass} shadow-2xs" title="点击切换 7 阶段跟进状态">
                        ${escapeHtml(status)}
                    </button>
                    ${status === '不合格' && disqReason ? `<span class="text-[10px] text-rose-600 max-w-[110px] truncate" title="${escapeHtml(disqReason)}">${escapeHtml(disqReason)}</span>` : ''}
                </div>
            </td>
            <td class="py-2.5 px-2.5 whitespace-nowrap text-right space-x-1" data-stop-propagation="true">
                <a href="${safeUrl}" target="_blank" rel="noopener noreferrer" class="inline-flex items-center px-2 py-1 rounded-md text-[11px] font-medium text-blue-700 bg-blue-50 hover:bg-blue-100 border border-blue-200 transition-colors" title="直接核验原帖">
                    核验原帖 ↗
                </a>
                <button type="button" id="drawer-trigger-${escapeHtml(lead.id)}" data-action="open-drawer" data-lead-id="${escapeHtml(lead.id)}" class="px-2 py-1 rounded-md text-[11px] font-semibold bg-zinc-900 text-white hover:bg-zinc-800 transition-colors shadow-xs">
                    核验详情
                </button>
            </td>
        </tr>`;
    }).join('');
}

function renderCards(leads) {
    const container = document.getElementById('cardViewWrapper');
    const emptyState = document.getElementById('empty-state');
    if (!container) return;

    if (leads.length === 0) {
        container.innerHTML = '';
        container.classList.add('hidden');
        emptyState.classList.remove('hidden');
        return;
    }

    emptyState.classList.add('hidden');
    container.classList.remove('hidden');

    container.innerHTML = leads.map(lead => {
        const status = getLeadStatus(lead.id);
        const statusClass = STATUS_CLASSES[status] || STATUS_CLASSES['未处理'];
        const logoHtml = getBrandLogoHtml(lead.competitor);
        const safeUrl = escapeHtml(sanitizeUrl(lead.url));
        const qm = lead.qualification_meta || {};
        const blockers = (qm.blocking_conditions || []).join('；');
        const st = evaluateLeadStages(lead, customBrandProfile);

        return `
        <div class="bg-white rounded-xl border border-zinc-200/90 p-4 shadow-xs hover:shadow-md transition-all cursor-pointer" data-action="open-drawer" data-lead-id="${escapeHtml(lead.id)}">
            <div class="flex flex-wrap items-center justify-between gap-2 pb-2.5 border-b border-zinc-100 mb-3" data-stop-propagation="true">
                <div class="flex items-center gap-2 flex-wrap">
                    <span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md text-xs font-bold bg-zinc-100 text-zinc-800 border border-zinc-200">
                        ${logoHtml}
                        <span>被替换标的：${escapeHtml(lead.competitor)}</span>
                    </span>
                    <span class="text-xs text-zinc-500 font-medium">${escapeHtml(st.stageLabel)}</span>
                    <span class="text-[11px] font-mono bg-zinc-100 text-zinc-600 px-1.5 py-0.5 rounded">ID: ${escapeHtml(lead.source_id)}</span>
                </div>
                <div class="flex items-center gap-2">
                    ${getScoreBadgeHtml(lead)}
                    <button type="button" data-action="cycle-status" data-lead-id="${escapeHtml(lead.id)}" class="px-2.5 py-0.5 rounded text-xs font-semibold border ${statusClass}">
                        ${escapeHtml(status)}
                    </button>
                </div>
            </div>

            <h3 class="text-sm font-bold text-zinc-900 mb-1.5">${escapeHtml(lead.title)}</h3>
            <div class="bg-zinc-50 p-2.5 rounded-lg border border-zinc-200/80 text-xs text-zinc-700 italic mb-2.5">
                原文关键证据：“${escapeHtml(lead.evidence_quote)}”
            </div>

            <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-2.5">
                ${renderProvenanceBadge(qm.team_scale, '团队规模')}
                ${renderProvenanceBadge(qm.budget_status, '预算状态')}
                ${renderProvenanceBadge(qm.decision_authority, '决策角色')}
                ${renderProvenanceBadge(qm.migration_urgency, '迁移期限')}
            </div>

            <div class="text-xs text-rose-800 bg-rose-50/70 border border-rose-200/70 rounded-lg px-3 py-1.5 mb-3">
                <strong>🚧 阻碍条件 / 待核验项：</strong>${escapeHtml(blockers)}
            </div>

            <div class="flex items-center justify-between pt-2.5 border-t border-zinc-100 text-xs" data-stop-propagation="true">
                <div class="flex items-center gap-3 text-zinc-500 font-mono text-[11px]">
                    <span>发布: ${escapeHtml(lead.timestamp)}</span>
                    <span>核验: ${escapeHtml(lead.collected_at)}</span>
                    <a href="${safeUrl}" target="_blank" rel="noopener noreferrer" class="text-blue-600 hover:underline font-sans font-semibold">打开原帖 (#${escapeHtml(lead.source_id)}) ↗</a>
                </div>
                <div class="flex items-center gap-2">
                    <button type="button" data-action="copy-lead-pitch" data-lead-id="${escapeHtml(lead.id)}" class="px-2.5 py-1 rounded-lg text-xs font-medium text-zinc-700 bg-white hover:bg-zinc-100 border border-zinc-200">
                        复制沟通草稿
                    </button>
                    <button type="button" id="card-trigger-${escapeHtml(lead.id)}" data-action="open-drawer" data-lead-id="${escapeHtml(lead.id)}" class="px-3 py-1 rounded-lg text-xs font-semibold bg-zinc-900 text-white hover:bg-zinc-800">
                        打开完整核验抽屉
                    </button>
                </div>
            </div>
        </div>`;
    }).join('');
}

function renderSplitView(leads) {
    const splitWrap = document.getElementById('splitViewWrapper');
    const listContainer = document.getElementById('splitLeadList');
    const countBadge = document.getElementById('splitCountBadge');
    const emptyState = document.getElementById('empty-state');
    if (!splitWrap || !listContainer) return;

    if (leads.length === 0) {
        listContainer.innerHTML = '';
        splitWrap.classList.add('hidden');
        emptyState.classList.remove('hidden');
        return;
    }

    emptyState.classList.add('hidden');
    splitWrap.classList.remove('hidden');

    if (countBadge) countBadge.innerText = `${leads.length} 条核验样本`;

    if (!leads.some(l => l.id === activeLeadId)) {
        activeLeadId = leads[0].id;
    }

    listContainer.innerHTML = leads.map(lead => {
        const status = getLeadStatus(lead.id);
        const logoHtml = getBrandLogoHtml(lead.competitor);
        const isSelected = (lead.id === activeLeadId);
        const st = evaluateLeadStages(lead, customBrandProfile);

        const itemClass = isSelected
            ? 'w-full text-left p-3 bg-emerald-50/80 border-l-4 border-l-emerald-600 transition-all cursor-pointer focus:outline-none focus:ring-2 focus:ring-inset focus:ring-zinc-900'
            : 'w-full text-left p-3 hover:bg-zinc-50 transition-all cursor-pointer border-l-4 border-l-transparent focus:outline-none focus:ring-2 focus:ring-inset focus:ring-zinc-900';

        return `
        <button type="button"
                id="split-item-${escapeHtml(lead.id)}"
                data-action="select-split-lead"
                data-lead-id="${escapeHtml(lead.id)}"
                aria-pressed="${isSelected ? 'true' : 'false'}"
                class="${itemClass}">
            <div class="flex items-center justify-between gap-1 mb-1">
                <div class="flex items-center gap-1.5 truncate">
                    <span class="inline-flex items-center gap-1 font-semibold text-zinc-900 text-xs">
                        ${logoHtml}
                        <span>${escapeHtml(lead.competitor)}</span>
                    </span>
                    <span class="text-[10px] text-zinc-400 font-mono">#${lead.idx} (ID:${escapeHtml(lead.source_id)})</span>
                </div>
                <div class="flex items-center gap-1">
                    ${getScoreBadgeHtml(lead)}
                </div>
            </div>
            <div class="text-xs font-semibold text-zinc-900 line-clamp-1 leading-snug mb-1">
                ${escapeHtml(lead.title)}
            </div>
            <div class="text-[11px] text-zinc-600 italic line-clamp-1 mb-1">
                “${escapeHtml(lead.evidence_quote)}”
            </div>
            <div class="flex items-center justify-between text-[10px] text-zinc-500">
                <span class="font-mono">${escapeHtml(lead.timestamp)}</span>
                <div class="flex items-center gap-1">
                    ${(customBrandProfile && customBrandProfile.brand_name && !st.s3Passed) ? `<span class="text-rose-600 font-semibold">⛔不匹配</span>` : ''}
                    <span class="px-1.5 py-0.2 rounded border border-zinc-200 bg-white">${escapeHtml(status)}</span>
                </div>
            </div>
        </button>`;
    }).join('');

    if (activeLeadId) {
        populateDetailPane('split', activeLeadId);
    }
}

function populateDetailPane(prefix, id) {
    const lead = LEADS_DATA.find(x => x.id === id);
    if (!lead) return;

    const logoHtml = getBrandLogoHtml(lead.competitor);
    const qm = lead.qualification_meta || {};
    const authorCandList = (lead.candidate_alternatives && lead.candidate_alternatives.length > 0)
        ? lead.candidate_alternatives.join(' / ')
        : '原文未提及特定候选';
    const sysRecList = (lead.system_recommended_alternatives && lead.system_recommended_alternatives.length > 0)
        ? `（系统推荐参考：${lead.system_recommended_alternatives.join(' / ')}）`
        : '';

    const titleEl = document.getElementById(`${prefix}Title`);
    const compBadgeEl = document.getElementById(`${prefix}CompetitorBadge`);
    const scoreBadgeEl = document.getElementById(`${prefix}ScoreBadge`);
    const authorEl = document.getElementById(`${prefix}Author`);
    const timestampEl = document.getElementById(`${prefix}Timestamp`);
    const collectedEl = document.getElementById(`${prefix}CollectedAt`);
    const engagementEl = document.getElementById(`${prefix}Engagement`);
    const contentEl = document.getElementById(`${prefix}Content`);
    const evidenceEl = document.getElementById(`${prefix}EvidenceQuote`);
    const sourceLinkEl = document.getElementById(`${prefix}SourceLink`);
    const provenanceGridEl = document.getElementById(`${prefix}ProvenanceGrid`);
    const blockersEl = document.getElementById(`${prefix}Blockers`);
    const contactPathEl = document.getElementById(`${prefix}ContactPath`);
    const churnBadgesEl = document.getElementById(`${prefix}ChurnBadges`);
    const execSumEl = document.getElementById(`${prefix}ExecutiveSummary`);
    const tacticsEl = document.getElementById(`${prefix}Tactics`);
    const objectionEl = document.getElementById(`${prefix}Objection`);

    if (titleEl) titleEl.innerText = lead.title;
    if (compBadgeEl) {
        compBadgeEl.innerHTML = `${logoHtml} <span>被替换竞品：${escapeHtml(lead.competitor)}</span> <span class="text-zinc-400">|</span> <span class="text-zinc-600 font-normal">原文提及候选：${escapeHtml(authorCandList)} ${escapeHtml(sysRecList)}</span>`;
    }
    if (scoreBadgeEl) scoreBadgeEl.innerHTML = getScoreBadgeHtml(lead);
    if (authorEl) authorEl.innerText = `发帖人：@${lead.author}`;
    if (timestampEl) timestampEl.innerText = `发布时间：${lead.timestamp}`;
    if (collectedEl) collectedEl.innerText = `核验时间：${lead.collected_at}`;
    if (engagementEl) engagementEl.innerText = `${lead.source} ID:${lead.source_id} (${lead.engagement})`;
    if (evidenceEl) evidenceEl.innerText = `“${lead.evidence_quote || lead.content}”`;
    if (contentEl) contentEl.innerText = lead.content;
    if (sourceLinkEl) sourceLinkEl.setAttribute('href', sanitizeUrl(lead.url));

    if (provenanceGridEl) {
        provenanceGridEl.innerHTML = [
            renderProvenanceBadge(qm.team_scale, '企业/团队规模'),
            renderProvenanceBadge(qm.budget_status, '预算与付费状态'),
            renderProvenanceBadge(qm.decision_authority, '选型决策角色'),
            renderProvenanceBadge(qm.migration_urgency, '迁移窗口与期限')
        ].join('');
    }

    if (blockersEl) {
        const bList = qm.blocking_conditions || ['需核验具体业务场景与数据迁移格式'];
        blockersEl.innerHTML = bList.map(b => `<li class="leading-relaxed">${escapeHtml(b)}</li>`).join('');
    }

    if (contactPathEl) {
        contactPathEl.innerText = qm.contact_path || '通过原帖发送中立核验问题核实未知维度';
    }

    if (churnBadgesEl) {
        churnBadgesEl.innerHTML = (lead.churn_drivers || []).map(d =>
            `<span class="px-2 py-0.5 rounded text-[11px] font-medium bg-zinc-100 text-zinc-700 border border-zinc-200">${escapeHtml(d)}</span>`
        ).join(' ');
    }

    if (execSumEl) execSumEl.innerText = lead.executive_summary || '';
    if (tacticsEl) tacticsEl.innerText = lead.tactical_action_plan || '';
    if (objectionEl) objectionEl.innerText = lead.objection_handling || '';

    if (prefix === 'drawer') {
        switchPitchTab(currentPitchTab || 'reply');
        updateDrawerStatusUI(getLeadStatus(id), getDisqualifyReason(id));
    } else {
        switchSplitPitchTab(currentSplitPitchTab || 'reply');
        updateSplitStatusUI(getLeadStatus(id), getDisqualifyReason(id));
    }
}

function applyRender() {
    initSessionStateFromStorage();
    const filtered = getFilteredAndSortedLeads();
    updateLiveCountsAndExportButtons(filtered);
    updateCategoryBadges();

    const tableWrap = document.getElementById('tableViewWrapper');
    const splitWrap = document.getElementById('splitViewWrapper');
    const cardWrap = document.getElementById('cardViewWrapper');

    if (tableWrap) tableWrap.classList.add('hidden');
    if (splitWrap) splitWrap.classList.add('hidden');
    if (cardWrap) cardWrap.classList.add('hidden');

    if (currentViewMode === 'table') {
        renderTable(filtered);
    } else if (currentViewMode === 'split') {
        renderSplitView(filtered);
    } else if (currentViewMode === 'cards') {
        renderCards(filtered);
    }
}
"""

CLIENT_WORKBENCH_EVENTS_JS = r"""
// ============================================================================
// 7. Accessible Drawer, Focus Restoration, Brand Capability Customizer & Events
// ============================================================================
function openDrawer(id, triggerEl = null) {
    const lead = LEADS_DATA.find(x => x.id === id);
    if (!lead) return;

    const sourceEl = triggerEl || document.activeElement;
    lastFocusedTrigger = {
        leadId: id,
        elementId: (sourceEl && sourceEl.id) ? sourceEl.id : '',
        action: (sourceEl && sourceEl.getAttribute) ? (sourceEl.getAttribute('data-action') || 'open-drawer') : 'open-drawer'
    };

    activeLeadId = id;
    applyRender();
    populateDetailPane('drawer', id);

    const mask = document.getElementById('detailDrawerMask');
    const drawer = document.getElementById('detailDrawer');
    if (mask) mask.classList.remove('hidden');
    if (drawer) {
        drawer.removeAttribute('hidden');
        drawer.removeAttribute('inert');
        drawer.setAttribute('aria-hidden', 'false');
        drawer.classList.remove('translate-x-full');
        const closeBtn = document.getElementById('drawerCloseBtn');
        if (closeBtn) closeBtn.focus();
    }
}

function closeDrawer() {
    const mask = document.getElementById('detailDrawerMask');
    const drawer = document.getElementById('detailDrawer');
    if (mask) mask.classList.add('hidden');
    if (drawer) {
        drawer.classList.add('translate-x-full');
        drawer.setAttribute('aria-hidden', 'true');
        drawer.setAttribute('inert', '');
        setTimeout(() => {
            if (drawer.classList.contains('translate-x-full')) {
                drawer.setAttribute('hidden', '');
            }
        }, 280);
    }
    const triggerInfo = lastFocusedTrigger;
    lastFocusedTrigger = null;
    activeLeadId = null;
    applyRender();

    // Restore focus to the freshly rendered element in live DOM (fixes detached DOM node focus bug)
    if (triggerInfo) {
        let targetEl = null;
        if (triggerInfo.elementId) {
            targetEl = document.getElementById(triggerInfo.elementId);
        }
        if (!targetEl && triggerInfo.leadId) {
            targetEl = document.getElementById('drawer-trigger-' + triggerInfo.leadId) ||
                       document.getElementById('card-trigger-' + triggerInfo.leadId) ||
                       document.querySelector(`button[data-action="open-drawer"][data-lead-id="${triggerInfo.leadId}"]`) ||
                       document.querySelector(`[data-action="open-drawer"][data-lead-id="${triggerInfo.leadId}"]`);
        }
        if (targetEl && typeof targetEl.focus === 'function') {
            targetEl.focus();
        }
    }
}

function selectSplitLead(id, shouldScroll = false) {
    activeLeadId = id;
    applyRender();
    if (shouldScroll) {
        const btn = document.getElementById('split-item-' + id);
        if (btn && typeof btn.scrollIntoView === 'function') {
            btn.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
            btn.focus({ preventScroll: true });
        }
    }
}

function switchPitchTab(tab) {
    currentPitchTab = tab;
    const btnReply = document.getElementById('btnPitchReply');
    const btnDev = document.getElementById('btnPitchDev');
    const btnExec = document.getElementById('btnPitchExec');
    const pitchEl = document.getElementById('drawerPitch');

    const activeCls = 'flex-1 py-1.5 px-2 rounded-md font-semibold text-zinc-900 bg-white shadow-2xs transition-all flex items-center justify-center gap-1';
    const inactiveCls = 'flex-1 py-1.5 px-2 rounded-md font-medium text-zinc-500 hover:text-zinc-800 transition-all flex items-center justify-center gap-1';

    if (btnReply) btnReply.className = (tab === 'reply') ? activeCls : inactiveCls;
    if (btnDev) btnDev.className = (tab === 'dev') ? activeCls : inactiveCls;
    if (btnExec) btnExec.className = (tab === 'exec') ? activeCls : inactiveCls;

    if (activeLeadId && pitchEl) {
        const lead = LEADS_DATA.find(x => x.id === activeLeadId);
        if (lead) pitchEl.innerText = getEffectivePitch(lead, tab);
    }
}

function switchSplitPitchTab(tab) {
    currentSplitPitchTab = tab;
    const btnReply = document.getElementById('btnSplitPitchReply');
    const btnDev = document.getElementById('btnSplitPitchDev');
    const btnExec = document.getElementById('btnSplitPitchExec');
    const pitchEl = document.getElementById('splitPitch');

    const activeCls = 'flex-1 py-1 px-2 rounded-md font-semibold text-zinc-900 bg-white shadow-2xs transition-all flex items-center justify-center gap-1';
    const inactiveCls = 'flex-1 py-1 px-2 rounded-md font-medium text-zinc-500 hover:text-zinc-800 transition-all flex items-center justify-center gap-1';

    if (btnReply) btnReply.className = (tab === 'reply') ? activeCls : inactiveCls;
    if (btnDev) btnDev.className = (tab === 'dev') ? activeCls : inactiveCls;
    if (btnExec) btnExec.className = (tab === 'exec') ? activeCls : inactiveCls;

    if (activeLeadId && pitchEl) {
        const lead = LEADS_DATA.find(x => x.id === activeLeadId);
        if (lead) pitchEl.innerText = getEffectivePitch(lead, tab);
    }
}

function updateDrawerStatusUI(status, disqReason) {
    const sel = document.getElementById('drawerStatusSelect');
    const reasonWrap = document.getElementById('drawerDisqualifyWrap');
    const reasonSel = document.getElementById('drawerDisqualifySelect');
    if (sel) sel.value = status;
    if (reasonWrap) {
        if (status === '不合格') {
            reasonWrap.classList.remove('hidden');
            if (reasonSel && disqReason) reasonSel.value = disqReason;
        } else {
            reasonWrap.classList.add('hidden');
        }
    }
}

function updateSplitStatusUI(status, disqReason) {
    const sel = document.getElementById('splitStatusSelect');
    const reasonWrap = document.getElementById('splitDisqualifyWrap');
    const reasonSel = document.getElementById('splitDisqualifySelect');
    if (sel) sel.value = status;
    if (reasonWrap) {
        if (status === '不合格') {
            reasonWrap.classList.remove('hidden');
            if (reasonSel && disqReason) reasonSel.value = disqReason;
        } else {
            reasonWrap.classList.add('hidden');
        }
    }
}

function toggleBrandCustomizer() {
    const bar = document.getElementById('brandCustomizerBar');
    if (!bar) return;
    bar.classList.toggle('hidden');
}

function renderBrandPresets() {
    const container = document.getElementById('brandPresetButtons');
    if (!container || !Array.isArray(BRAND_PRESETS_DATA)) return;
    container.innerHTML = BRAND_PRESETS_DATA.map(p => `
        <button type="button" data-action="select-brand-preset" data-preset-id="${escapeHtml(p.id)}" class="px-2.5 py-1 rounded-full text-[11px] font-medium bg-white hover:bg-emerald-50 text-zinc-700 hover:text-emerald-700 border border-zinc-200 hover:border-emerald-300 transition-all shadow-2xs">
            ${escapeHtml(p.label)}
        </button>
    `).join('');
}

function selectBrandPreset(presetId) {
    const preset = (BRAND_PRESETS_DATA || []).find(p => p.id === presetId);
    if (!preset) return;
    const nameInput = document.getElementById('customBrandName');
    const roleSelect = document.getElementById('customActorRole');
    const compInput = document.getElementById('customTargetCompetitors');
    const capInput = document.getElementById('customApprovedCaps');
    const limitInput = document.getElementById('customKnownLimits');
    const linkInput = document.getElementById('customBrandLink');

    if (nameInput) nameInput.value = preset.brand_name || '';
    if (roleSelect && preset.actor_role) roleSelect.value = preset.actor_role;
    if (compInput) compInput.value = (preset.target_competitors || []).join(', ');
    if (capInput) capInput.value = preset.approved_capabilities || '';
    if (limitInput) limitInput.value = preset.known_limitations || '';
    if (linkInput) linkInput.value = preset.cta_link || '';
    applyCustomBrandProfile();
}

function applyCustomBrandProfile() {
    const nameVal = (document.getElementById('customBrandName')?.value || '').trim();
    const roleVal = (document.getElementById('customActorRole')?.value || '产品研发团队').trim();
    const compRaw = (document.getElementById('customTargetCompetitors')?.value || '').trim();
    const capVal = (document.getElementById('customApprovedCaps')?.value || '').trim();
    const limitVal = (document.getElementById('customKnownLimits')?.value || '').trim();
    const linkVal = (document.getElementById('customBrandLink')?.value || '').trim();
    const indicator = document.getElementById('activeBrandIndicator');

    if (!nameVal) {
        customBrandProfile = null;
        if (indicator) {
            indicator.innerText = '当前视角：默认中立证据核验（阶段3待绑定卖方能力·仅生成中立问题）';
            indicator.className = 'text-[11px] font-medium text-zinc-600 bg-zinc-100 border border-zinc-200 px-2 py-0.5 rounded-md';
        }
        applyRender();
        if (activeLeadId) {
            populateDetailPane('drawer', activeLeadId);
            populateDetailPane('split', activeLeadId);
        }
        showToast('已切换为【默认中立核验视角】（仅输出中立核验问题，不承诺卖方能力）');
        return;
    }

    // CRITICAL (Audit Finding #6): Do NOT default empty target_competitors to ['*'] or auto-fabricate capabilities!
    const parsedTargets = compRaw
        ? compRaw.split(/[,，/]/).map(s => s.trim()).filter(s => s && s !== '*')
        : [];

    customBrandProfile = {
        brand_name: nameVal,
        actor_role: roleVal || '产品研发团队',
        target_competitors: parsedTargets,
        approved_capabilities: capVal,
        known_limitations: limitVal || '具体生产环境适配边界需结合贵司实际数据量级核实',
        cta_link: linkVal
    };

    if (parsedTargets.length === 0 || !capVal) {
        if (indicator) {
            indicator.innerText = `⚠️ 卖方档案未完整配置：${nameVal}（需填写适配竞品与已核准能力）`;
            indicator.className = 'text-[11px] font-semibold text-rose-800 bg-rose-50 border border-rose-200 px-2 py-0.5 rounded-md';
        }
        applyRender();
        if (activeLeadId) {
            populateDetailPane('drawer', activeLeadId);
            populateDetailPane('split', activeLeadId);
        }
        showToast(`请补充填写【${nameVal}】的「适配被替换竞品」与「已核准真实能力」，系统禁止通配符或自动补造能力`, true);
        return;
    }

    if (indicator) {
        indicator.innerText = `已启用卖方能力门控：${nameVal} (${customBrandProfile.actor_role} · 仅适配 ${customBrandProfile.target_competitors.join('/')})`;
        indicator.className = 'text-[11px] font-semibold text-emerald-800 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-md';
    }

    applyRender();
    if (activeLeadId) {
        populateDetailPane('drawer', activeLeadId);
        populateDetailPane('split', activeLeadId);
    }
    showToast(`已启用【${nameVal}】阶段 3 能力门控（非匹配赛道与未知权限将自动拦截推荐）`);
}

function setFilterCategory(cat, btn) {
    currentCategory = cat;
    document.querySelectorAll('.nav-btn').forEach(b => {
        b.classList.remove('bg-zinc-800', 'text-white', 'font-semibold');
        b.classList.add('text-zinc-400', 'font-medium');
    });
    document.querySelectorAll('.mobile-nav-btn').forEach(b => {
        b.classList.remove('bg-zinc-800', 'text-white');
        b.classList.add('text-zinc-400');
    });

    if (btn) {
        if (btn.classList.contains('nav-btn')) {
            btn.classList.add('bg-zinc-800', 'text-white', 'font-semibold');
            btn.classList.remove('text-zinc-400', 'font-medium');
        } else if (btn.classList.contains('mobile-nav-btn')) {
            btn.classList.add('bg-zinc-800', 'text-white');
            btn.classList.remove('text-zinc-400');
        }
    }
    applyRender();
}

function filterByCompetitor(comp, btn) {
    currentCompetitor = comp;
    document.querySelectorAll('.comp-pill').forEach(b => {
        b.classList.remove('bg-zinc-900', 'text-white', 'font-semibold');
        b.classList.add('bg-white', 'text-zinc-700', 'border-zinc-200');
    });
    if (btn) {
        btn.classList.add('bg-zinc-900', 'text-white', 'font-semibold');
        btn.classList.remove('bg-white', 'text-zinc-700', 'border-zinc-200');
    }
    applyRender();
}

function setViewMode(mode) {
    currentViewMode = mode;
    const btnTable = document.getElementById('btnViewTable');
    const btnSplit = document.getElementById('btnViewSplit');
    const btnCards = document.getElementById('btnViewCards');

    [btnTable, btnSplit, btnCards].forEach(b => {
        if (b) b.className = 'px-2.5 py-1 rounded-md font-medium text-zinc-600 hover:text-zinc-900 transition-all flex items-center gap-1 whitespace-nowrap';
    });

    if (mode === 'table' && btnTable) {
        btnTable.className = 'px-2.5 py-1 rounded-md font-semibold text-zinc-900 bg-white shadow-xs transition-all flex items-center gap-1 whitespace-nowrap';
    } else if (mode === 'split' && btnSplit) {
        btnSplit.className = 'px-2.5 py-1 rounded-md font-semibold text-zinc-900 bg-white shadow-xs transition-all flex items-center gap-1 whitespace-nowrap';
        const filtered = getFilteredAndSortedLeads();
        if (!activeLeadId && filtered.length > 0) activeLeadId = filtered[0].id;
    } else if (mode === 'cards' && btnCards) {
        btnCards.className = 'px-2.5 py-1 rounded-md font-semibold text-zinc-900 bg-white shadow-xs transition-all flex items-center gap-1 whitespace-nowrap';
    }
    applyRender();
}

function toggleSort(field) {
    if (currentSortField === field) {
        currentSortDir = (currentSortDir === 'desc') ? 'asc' : 'desc';
    } else {
        currentSortField = field;
        currentSortDir = (field === 'idx') ? 'asc' : 'desc';
    }
    const elScore = document.getElementById('sortIndicatorScore');
    const elIdx = document.getElementById('sortIndicatorIdx');
    if (elScore) elScore.innerText = currentSortField === 'score' ? (currentSortDir === 'desc' ? '↓' : '↑') : '↕';
    if (elIdx) elIdx.innerText = currentSortField === 'idx' ? (currentSortDir === 'desc' ? '↓' : '↑') : '↕';
    applyRender();
}

function handleSearch() {
    const val = (document.getElementById('searchInput')?.value || '').trim();
    const clearBtn = document.getElementById('searchClearBtn');
    if (clearBtn) {
        if (val.length > 0) clearBtn.classList.remove('hidden');
        else clearBtn.classList.add('hidden');
    }
    applyRender();
}

function clearSearch() {
    const input = document.getElementById('searchInput');
    if (input) {
        input.value = '';
        input.focus();
    }
    document.getElementById('searchClearBtn')?.classList.add('hidden');
    applyRender();
}

function resetAllFilters() {
    const input = document.getElementById('searchInput');
    if (input) input.value = '';
    document.getElementById('searchClearBtn')?.classList.add('hidden');
    currentCategory = 'all';
    currentCompetitor = 'ALL';
    currentSortField = 'default';
    currentSortDir = 'desc';

    document.querySelectorAll('.comp-pill').forEach((b, idx) => {
        if (idx === 0) {
            b.classList.add('bg-zinc-900', 'text-white', 'font-semibold');
            b.classList.remove('bg-white', 'text-zinc-700', 'border-zinc-200');
        } else {
            b.classList.remove('bg-zinc-900', 'text-white', 'font-semibold');
            b.classList.add('bg-white', 'text-zinc-700', 'border-zinc-200');
        }
    });
    document.querySelectorAll('.nav-btn').forEach((b, idx) => {
        if (idx === 0) {
            b.classList.add('bg-zinc-800', 'text-white', 'font-semibold');
            b.classList.remove('text-zinc-400', 'font-medium');
        } else {
            b.classList.remove('bg-zinc-800', 'text-white', 'font-semibold');
            b.classList.add('text-zinc-400', 'font-medium');
        }
    });
    applyRender();
}

let modalTriggerEl = null;
function openHowItWorksModal(triggerEl = null) {
    modalTriggerEl = triggerEl || document.activeElement;
    const modalMask = document.getElementById('howItWorksMask');
    if (modalMask) {
        modalMask.classList.remove('hidden');
        modalMask.removeAttribute('hidden');
        modalMask.setAttribute('aria-hidden', 'false');
        const closeBtn = document.getElementById('howItWorksCloseBtn');
        if (closeBtn) closeBtn.focus();
    }
}

function closeHowItWorksModal() {
    const modalMask = document.getElementById('howItWorksMask');
    if (modalMask) {
        modalMask.classList.add('hidden');
        modalMask.setAttribute('hidden', '');
        modalMask.setAttribute('aria-hidden', 'true');
    }
    if (modalTriggerEl && typeof modalTriggerEl.focus === 'function') {
        modalTriggerEl.focus();
        modalTriggerEl = null;
    }
}

let toastTimeout = null;
function showToast(message, isError = false) {
    const toast = document.getElementById('toastNotification');
    const toastMsg = document.getElementById('toastMessage');
    const toastIcon = document.getElementById('toastIcon');
    if (!toast || !toastMsg || !toastIcon) return;

    if (toastTimeout) {
        clearTimeout(toastTimeout);
        toastTimeout = null;
    }
    toastMsg.innerText = message;
    toastIcon.innerHTML = isError
        ? `<svg class="w-4 h-4 text-rose-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>`
        : `<svg class="w-4 h-4 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>`;

    toast.classList.remove('translate-y-24', 'opacity-0');
    toastTimeout = setTimeout(() => {
        toast.classList.add('translate-y-24', 'opacity-0');
    }, 2800);
}

function copyToClipboard(text, successMsg = '已复制到剪贴板！', btnElement = null) {
    if (!text) return;
    const onCopySuccess = () => {
        if (btnElement) {
            const origHtml = btnElement.innerHTML;
            btnElement.innerHTML = `<span class="text-emerald-700 font-bold">✓ 已复制</span>`;
            setTimeout(() => { btnElement.innerHTML = origHtml; }, 1600);
        }
        showToast(successMsg);
    };
    if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(onCopySuccess).catch(() => fallbackCopy(text, onCopySuccess));
    } else {
        fallbackCopy(text, onCopySuccess);
    }
}

function fallbackCopy(text, onSuccess) {
    try {
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        ta.setAttribute('readonly', '');
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        if (onSuccess) onSuccess();
    } catch (e) {
        showToast('复制失败，请手动复制文本', true);
    }
}

function updateCategoryBadges() {
    const total = LEADS_DATA.length;
    const highIntent = LEADS_DATA.filter(isHighIntentLead).length;
    const caution = LEADS_DATA.filter(isCautionOrPendingLead).length;
    const pricing = LEADS_DATA.filter(isPricingDriverLead).length;
    const privacy = LEADS_DATA.filter(isPrivacyDriverLead).length;

    const setBadge = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.innerText = val;
    };
    setBadge('badgeCountAll', total);
    setBadge('badgeCountHigh', highIntent);
    setBadge('badgeCountCaution', caution);
    setBadge('badgeCountPricing', pricing);
    setBadge('badgeCountPrivacy', privacy);
}

// Event Delegation for all dynamic lead rows/cards/buttons
document.addEventListener('click', (e) => {
    const stopEl = e.target.closest('[data-stop-propagation="true"]');
    const actionEl = e.target.closest('[data-action]');
    if (!actionEl) return;

    if (stopEl && !actionEl.contains(stopEl)) {
        e.stopPropagation();
    }

    const action = actionEl.getAttribute('data-action');
    const leadId = actionEl.getAttribute('data-lead-id');

    if (action === 'open-drawer' && leadId) {
        openDrawer(leadId, actionEl);
    } else if (action === 'cycle-status' && leadId) {
        e.stopPropagation();
        cycleStatus(leadId);
    } else if (action === 'select-split-lead' && leadId) {
        selectSplitLead(leadId, false);
    } else if (action === 'copy-lead-pitch' && leadId) {
        e.stopPropagation();
        const lead = LEADS_DATA.find(x => x.id === leadId);
        if (lead) {
            copyToClipboard(getEffectivePitch(lead, 'reply'), `已复制 #${lead.idx} 沟通草稿`, actionEl);
        }
    } else if (action === 'select-brand-preset') {
        const presetId = actionEl.getAttribute('data-preset-id');
        if (presetId) selectBrandPreset(presetId);
    } else if (action === 'filter-competitor') {
        const comp = actionEl.getAttribute('data-competitor');
        if (comp) filterByCompetitor(comp, actionEl);
    }
});

// Delegated change listener for 7-stage CRM status and disqualification reason selects
document.addEventListener('change', (e) => {
    const target = e.target;
    if (!target) return;
    if (target.id === 'drawerStatusSelect' || target.id === 'splitStatusSelect') {
        if (activeLeadId) {
            setLeadStatus(activeLeadId, target.value);
        }
    } else if (target.id === 'drawerDisqualifySelect' || target.id === 'splitDisqualifySelect') {
        if (activeLeadId) {
            setLeadStatus(activeLeadId, '不合格', target.value);
        }
    }
});

// Keyboard navigation & Modal Focus Trap
document.addEventListener('keydown', (e) => {
    if (e.isComposing || e.keyCode === 229) return;

    const howItWorks = document.getElementById('howItWorksMask');
    const drawer = document.getElementById('detailDrawer');
    const isModalOpen = Boolean(howItWorks && !howItWorks.classList.contains('hidden'));
    const isDrawerOpen = Boolean(drawer && !drawer.classList.contains('translate-x-full'));

    if (e.key === 'Escape') {
        if (isModalOpen) {
            e.preventDefault();
            closeHowItWorksModal();
            return;
        }
        if (isDrawerOpen) {
            e.preventDefault();
            closeDrawer();
            return;
        }
        const searchInput = document.getElementById('searchInput');
        if (searchInput && searchInput.value) {
            clearSearch();
            return;
        }
    }

    // Focus trap inside active dialog (Modal or Drawer)
    if (e.key === 'Tab' && (isModalOpen || isDrawerOpen)) {
        const container = isModalOpen ? document.getElementById('howItWorksModal') : drawer;
        if (container) {
            const focusables = Array.from(container.querySelectorAll(
                'a[href], button:not([disabled]), select:not([disabled]), textarea:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])'
            )).filter(el => el.offsetParent !== null);
            if (focusables.length > 0) {
                const first = focusables[0];
                const last = focusables[focusables.length - 1];
                if (e.shiftKey && document.activeElement === first) {
                    e.preventDefault();
                    last.focus();
                } else if (!e.shiftKey && document.activeElement === last) {
                    e.preventDefault();
                    first.focus();
                }
            }
        }
        return;
    }

    // Do NOT allow background shortcuts (/ or Arrow keys) when a modal or drawer dialog is open!
    if (isModalOpen || isDrawerOpen) return;

    const activeTag = (document.activeElement && document.activeElement.tagName) ? document.activeElement.tagName.toUpperCase() : '';
    const isEditable = ['INPUT', 'TEXTAREA', 'SELECT'].includes(activeTag) || (document.activeElement && document.activeElement.isContentEditable);

    if (!isEditable && (e.key === '/' || ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k'))) {
        e.preventDefault();
        const searchInput = document.getElementById('searchInput');
        if (searchInput) {
            searchInput.focus();
            searchInput.select();
        }
        return;
    }

    if (!isEditable && currentViewMode === 'split') {
        if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
            e.preventDefault();
            const leads = getFilteredAndSortedLeads();
            if (leads.length > 0) {
                const curIdx = leads.findIndex(l => l.id === activeLeadId);
                const nextIdx = (e.key === 'ArrowDown')
                    ? (curIdx < leads.length - 1 ? curIdx + 1 : 0)
                    : (curIdx > 0 ? curIdx - 1 : leads.length - 1);
                selectSplitLead(leads[nextIdx].id, true);
            }
        }
    }
});

document.addEventListener('DOMContentLoaded', () => {
    initSessionStateFromStorage();
    updateCategoryBadges();
    renderBrandPresets();
    applyRender();
});
"""


def get_full_client_js() -> str:
    return CLIENT_WORKBENCH_JS + "\n" + CLIENT_WORKBENCH_UI_JS + "\n" + CLIENT_WORKBENCH_EVENTS_JS


def render_internal_bd_html(
    pilot_offers: List[Dict],
    seed_clients: List[Dict],
    launch_campaigns: List[Dict],
    compiled_css: str = "",
) -> str:
    """
    Renders the standalone Internal BD & Self-Operation Playbook (`internal_bd_ops.html`).
    Every seed client entry displays separated `verbatim_evidence_record`, `analysis_summary`, and `recommended_next_step`.
    """
    import html as _html

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    offers_html = ""
    for offer in pilot_offers:
        deliv_items = "".join(
            f'<li class="text-xs text-zinc-700 leading-relaxed">{_html.escape(d)}</li>'
            for d in offer.get("deliverables", [])
        )
        offers_html += f"""
        <div class="bg-white rounded-xl border border-zinc-200 p-5 shadow-xs flex flex-col justify-between space-y-3">
            <div class="space-y-2">
                <div class="flex items-center justify-between gap-2">
                    <span class="px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-50 text-emerald-800 border border-emerald-200">{_html.escape(offer['tier'])}</span>
                    <span class="text-base font-bold font-mono text-zinc-900">{_html.escape(offer['price'])}</span>
                </div>
                <h3 class="text-sm font-bold text-zinc-900">{_html.escape(offer['name'])}</h3>
                <p class="text-xs text-zinc-600"><strong>目标客群 (ICP)：</strong>{_html.escape(offer['target_icp'])}</p>
                <p class="text-xs text-zinc-600"><strong>监控范围：</strong>{_html.escape(offer['scope'])}</p>
                <div class="pt-1">
                    <div class="text-xs font-bold text-zinc-800 mb-1">标准交付物：</div>
                    <ul class="list-disc pl-4 space-y-1">{deliv_items}</ul>
                </div>
            </div>
            <div class="p-2.5 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-900">
                <strong>🛡️ 验收与退款保障：</strong>{_html.escape(offer['sla_guarantee'])}
            </div>
        </div>
        """

    clients_html = ""
    for idx, client in enumerate(seed_clients, 1):
        rec = client.get("verbatim_evidence_record", {})
        clients_html += f"""
        <div class="bg-white rounded-xl border border-zinc-200 p-5 shadow-xs space-y-3">
            <div class="flex items-start justify-between gap-2">
                <div>
                    <span class="text-xs font-mono font-bold text-zinc-500">#{idx} · 关联真实证据 ID: {_html.escape(client.get('verified_evidence_id', ''))} (@{_html.escape(rec.get('author', ''))} · {_html.escape(rec.get('timestamp', ''))})</span>
                    <h4 class="text-sm font-bold text-zinc-900">{_html.escape(client['name'])}</h4>
                    <p class="text-xs text-zinc-500">{_html.escape(client['category'])} · 阶段：{_html.escape(client['stage'])}</p>
                </div>
                <span class="px-2.5 py-0.5 rounded text-xs font-semibold bg-zinc-100 text-zinc-800 border border-zinc-200">
                    被替换竞品：{_html.escape(client['target_incumbent'])}
                </span>
            </div>
            <div class="text-xs text-emerald-900 bg-emerald-50/70 p-2.5 rounded-lg border border-emerald-200 space-y-1">
                <div><strong>1. 逐字原文证据 (Verbatim Quote)：</strong>“{_html.escape(rec.get('verbatim_quote', ''))}”</div>
                <div class="font-mono text-[11px] text-emerald-700">原帖标题：{_html.escape(rec.get('title', ''))} | 链接：{_html.escape(rec.get('url', ''))}</div>
            </div>
            <p class="text-xs text-zinc-700 bg-zinc-50 p-2.5 rounded-lg border border-zinc-200">
                <strong>2. 资格核验归纳 (Analysis Summary)：</strong>{_html.escape(client.get('analysis_summary', client['pain_point']))}
            </p>
            <p class="text-xs text-blue-900 bg-blue-50/70 p-2.5 rounded-lg border border-blue-200">
                <strong>3. 建议跟进动作 (Recommended Action)：</strong>{_html.escape(client.get('recommended_next_step', ''))}
            </p>
            <pre class="bg-zinc-950 text-zinc-100 p-3.5 rounded-xl text-xs font-mono whitespace-pre-wrap leading-relaxed select-all">{_html.escape(client['bd_pitch'])}</pre>
            <div class="text-[11px] text-zinc-500">建议触达渠道：{_html.escape(client['contact_channel'])}</div>
        </div>
        """

    campaigns_html = ""
    for camp in launch_campaigns:
        campaigns_html += f"""
        <div class="bg-white rounded-xl border border-zinc-200 p-5 shadow-xs space-y-2.5">
            <div class="flex items-center justify-between gap-2">
                <span class="px-2.5 py-0.5 rounded text-xs font-bold bg-zinc-900 text-white">{_html.escape(camp['channel'])}</span>
                <span class="text-xs text-emerald-700 font-medium">{_html.escape(camp['best_time'])}</span>
            </div>
            <h4 class="text-sm font-bold text-zinc-900">{_html.escape(camp['title'])}</h4>
            <pre class="bg-zinc-50 p-3.5 rounded-xl border border-zinc-200 text-xs text-zinc-800 font-mono whitespace-pre-wrap leading-relaxed select-all">{_html.escape(camp['content'])}</pre>
        </div>
        """

    style_block = f"<style>{compiled_css}</style>" if compiled_css else '<script src="https://cdn.tailwindcss.com"></script>'

    return f"""<!DOCTYPE html>
<html lang="zh-CN" class="bg-zinc-50">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IntentRadar · 内部 BD 与单赛道试点运营手册 (Internal Only)</title>
    {style_block}
</head>
<body class="font-sans antialiased text-zinc-900 p-6 max-w-6xl mx-auto space-y-8">
    <header class="bg-zinc-950 text-white p-6 rounded-2xl border border-zinc-800 space-y-2">
        <div class="flex items-center justify-between flex-wrap gap-2">
            <span class="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                🔒 内部运营后台文档 · 已与客户交付工作台物理隔离至非公开目录
            </span>
            <span class="text-xs font-mono text-zinc-400">生成时间：{now_str}</span>
        </div>
        <h1 class="text-lg font-bold">IntentRadar · 诚实证据流 BD 与单赛道人工核验试点手册 (v3.1)</h1>
        <p class="text-xs text-zinc-300 leading-relaxed">
            本页面由已核验的 `IntentSignal` 记录动态生成，严格分离：① 逐字原文证据 (Verbatim Quote)、② 资格核验归纳 (Analysis Summary)、③ 建议动作 (Recommended Action)。
        </p>
    </header>

    <section class="space-y-3">
        <h2 class="text-base font-bold text-zinc-900">一、三档单赛道人工核验试点报价与退款兜底条款</h2>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
            {offers_html}
        </div>
    </section>

    <section class="space-y-3">
        <h2 class="text-base font-bold text-zinc-900">二、1对1 卖方开发名录（动态读取 mock_data.py 同一条已核验记录）</h2>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            {clients_html}
        </div>
    </section>

    <section class="space-y-3">
        <h2 class="text-base font-bold text-zinc-900">三、真实角色利益披露模板</h2>
        <div class="grid grid-cols-1 gap-4">
            {campaigns_html}
        </div>
    </section>
</body>
</html>"""
