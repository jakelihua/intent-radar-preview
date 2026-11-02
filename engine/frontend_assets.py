"""
Frontend JS Controller, Pure-JS OpenXML (.xlsx) Generator, and Internal BD Playbook Renderer.
Separates data validation, filtering, capability-gated outreach, explicit export, and accessible UI events.
"""

import json
from datetime import datetime
from typing import Dict, List


CLIENT_WORKBENCH_JS = r"""
// ============================================================================
// 1. Security, URL Validation & OWASP Spreadsheet Sanitization
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

// OWASP CSV / Spreadsheet Formula Injection Prevention
function sanitizeSpreadsheetCell(val) {
    if (val === null || val === undefined) return '';
    let str = String(val).replace(/\r\n/g, '\n').replace(/\r/g, '\n');
    const trimmedLeft = str.replace(/^\s+/, '');
    if (trimmedLeft.length > 0 && /^[=+\-@]/.test(trimmedLeft)) {
        return "'" + str;
    }
    if (/^[\t\r]/.test(str)) {
        return "'" + str;
    }
    return str;
}

// ============================================================================
// 2. Unified State & 7-Stage Qualification Funnel
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
let lastFocusedElement = null;

// In-memory fallback if localStorage is blocked or quota-exceeded
const memoryStatusStore = {};
const memoryDisqualifyReasonStore = {};

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

function getLeadStatus(id) {
    try {
        const val = localStorage.getItem('ir_lead_status_' + id);
        if (val && QUALIFICATION_STATUSES.includes(val)) return val;
    } catch (e) {}
    return memoryStatusStore[id] || '未处理';
}

function getDisqualifyReason(id) {
    try {
        const val = localStorage.getItem('ir_lead_disq_' + id);
        if (val) return val;
    } catch (e) {}
    return memoryDisqualifyReasonStore[id] || '';
}

function setLeadStatus(id, newStatus, reason = null) {
    if (!QUALIFICATION_STATUSES.includes(newStatus)) return;
    memoryStatusStore[id] = newStatus;
    if (reason !== null) {
        memoryDisqualifyReasonStore[id] = reason;
    } else if (newStatus === '不合格' && !getDisqualifyReason(id)) {
        const lead = LEADS_DATA.find(x => x.id === id);
        const defaultReason = (lead && lead.intent_score < 68)
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
        showToast(`本地存储受限（localStorage 写入失败），状态【${newStatus}】仅在当前会话生效`, true);
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

// ============================================================================
// 3. Cross-Category Brand Capability Gating & Honest Outreach Generator
// ============================================================================
function hasReplacementAuthority(lead) {
    if (!lead) return false;
    const authVal = (lead.qualification_meta && lead.qualification_meta.decision_authority && lead.qualification_meta.decision_authority.value) || '';
    if (authVal.includes('无采购与替换决策权') || authVal.includes('无选型决定权') || lead.intent_score < 68) {
        return false;
    }
    return true;
}

function checkBrandCompatibility(lead, profile) {
    if (!profile || !profile.brand_name) {
        return { compatible: true, mode: 'neutral' };
    }
    const targets = profile.target_competitors || ['*'];
    if (targets.includes('*')) {
        return { compatible: true, mode: 'custom_wildcard' };
    }
    const leadCompLower = (lead.competitor || '').toLowerCase();
    const isMatch = targets.some(t => {
        const tl = t.toLowerCase();
        return leadCompLower.includes(tl) || tl.includes(leadCompLower);
    });
    if (!isMatch) {
        return {
            compatible: false,
            mode: 'mismatch',
            reason: `当前已选卖方产品为【${profile.brand_name}】（仅适配替换：${targets.join(' / ')}），而本条线索被替换标的为【${lead.competitor}】（${lead.category}）。跨赛道强行套用话术已被系统拦截。`
        };
    }
    return { compatible: true, mode: 'matched' };
}

function getEffectivePitch(lead, type = 'reply') {
    if (!lead) return '';

    // 1. Check if lead explicitly lacks replacement decision authority
    if (!hasReplacementAuthority(lead)) {
        const quote = lead.evidence_quote || lead.content || '';
        return `⚠️ 【资格核验拦截 · 不建议直接发送推销话术】\n` +
               `原因：原帖作者 @${lead.author} 在正文中明确表示 "${quote}"（无工具选型与替换决策权）。\n` +
               `建议动作：将该帖标记为「不合格（原因：无替换决策权）」，仅保留痛点作为产品研发参考，避免无效打扰。`;
    }

    // 2. If no custom brand is active, return neutral evidence-backed qualification draft
    if (!customBrandProfile || !customBrandProfile.brand_name) {
        if (type === 'dev') return lead.pitch_dev || lead.suggested_pitch || '';
        if (type === 'exec') return lead.pitch_exec || lead.suggested_pitch || '';
        return lead.public_reply || '';
    }

    // 3. Check Cross-Category Brand Capability Compatibility
    const compat = checkBrandCompatibility(lead, customBrandProfile);
    if (!compat.compatible) {
        return `⛔ 【跨赛道能力不匹配 · 已禁止生成推荐话术】\n${compat.reason}\n💡 解决方案：请在上方「卖方产品能力档案」中切换至适配【${lead.competitor}】的预设，或切回「默认中立核验视角」。`;
    }

    // 4. Honest, Evidence-Grounded Outreach using ONLY approved capabilities & explicit unknown blockers
    const bName = customBrandProfile.brand_name;
    const bCaps = customBrandProfile.approved_capabilities || '标准数据导入与可预测的商业授权';
    const bLimits = customBrandProfile.known_limitations || '具体生产环境兼容性仍需根据贵司实际架构核实';
    const bLink = customBrandProfile.cta_link || '';
    const evidenceSnippet = (lead.evidence_quote || lead.title || '').slice(0, 120);
    const blockers = (lead.qualification_meta && lead.qualification_meta.blocking_conditions && lead.qualification_meta.blocking_conditions.length > 0)
        ? lead.qualification_meta.blocking_conditions.join('；')
        : '具体席位规模与现有历史数据迁移边界待确认';

    if (type === 'reply') {
        return `利益相关披露：我参与了【${bName}】的开发。\n` +
               `针对你在原帖提到的「${evidenceSnippet}」，我们目前已核准支持的能力包括：${bCaps}。\n` +
               `但需要客观说明已知边界：【${bLimits}】；同时原帖尚未涉及【${blockers}】，仍需结合你们的具体场景确认。\n` +
               `${bLink ? '这里有对应的迁移核验文档：' + bLink + ' ，' : ''}建议先用一小份脱敏数据做最小化验证。`;
    } else if (type === 'dev') {
        return `Hi @${lead.author}，在 ${lead.source} 看到你关于 ${lead.competitor} 的讨论（原帖提及：“${evidenceSnippet}”）。\n` +
               `先做利益相关披露：我负责【${bName}】的研发。针对该场景，我们已支持：${bCaps}。\n` +
               `在判断是否适合你们团队前，想先请教并确认两个边界问题：1) ${bLimits}；2) ${blockers}。\n` +
               `${bLink ? '迁移验证指南参考：' + bLink : '方便的话可以先跑一下沙箱导入测试。'}`;
    } else {
        return `您好 @${lead.author}，关注到贵团队在 ${lead.source} 评估 ${lead.competitor} 的替代方案。\n` +
               `我是【${bName}】团队成员（利益相关披露）。对照原帖提到的痛点，我方已核准支持：${bCaps}。\n` +
               `目前尚待确认的阻碍条件包括：【${blockers}】以及【${bLimits}】。建议先安排 15 分钟技术边界核对或小样本导入测试，确认完全匹配后再评估商务方案。`;
    }
}

// ============================================================================
// 4. Unified Filtering & Sorting Predicates
// ============================================================================
function isHighIntentLead(item) {
    return item.intent_score >= 80 && hasReplacementAuthority(item);
}

function isCautionOrPendingLead(item) {
    return item.intent_score < 80 || !hasReplacementAuthority(item);
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
        lv.setUint16(6, 0x0800, true); // UTF-8 flag
        lv.setUint16(8, 0, true);      // STORE (no compression)
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
    // Strip invalid XML control chars except \t, \n, \r
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
        const safeText = escapeXmlText(sanitizeSpreadsheetCell(h));
        return `<c r="${ref}" s="1" t="inlineStr"><is><t xml:space="preserve">${safeText}</t></is></c>`;
    }).join('');

    const dataRowsXml = rows.map((row, rIdx) => {
        const rowNum = rIdx + 2;
        const cellsXml = row.map((cellVal, cIdx) => {
            const ref = `${excelColName(cIdx)}${rowNum}`;
            const safeText = escapeXmlText(sanitizeSpreadsheetCell(cellVal));
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
        '资格核验阶段', '意向评分', '被替换竞品(Incumbent)', '提及候选方案(Candidates)',
        '原帖标题', '原文关键证据摘录', '发帖人账号',
        '团队规模及来源', '预算状态及来源', '决策权限及来源', '迁移急迫度及来源',
        '待核验阻碍条件', '建议触达路径', '跟进状态', '不合格原因',
        '公开透明利益披露回复', '1v1技术核验草稿', '商业可行性核验草稿', '原帖直达链接'
    ];
    const colWidths = [
        6, 14, 14, 18, 18,
        24, 10, 18, 22,
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
        return [
            String(l.idx),
            l.source || '',
            l.source_id || l.id || '',
            l.timestamp || '',
            l.collected_at || '',
            l.qualification_stage || '',
            `${l.intent_score}分`,
            l.competitor || '',
            (l.candidate_alternatives || []).join(', ') || '未点名特定候选',
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
        showToast(`已导出真实 .xlsx 核验台账（${scope === 'all' ? '全库' : '当前筛选'} ${leads.length} 条，含冻结首行、筛选器与公式防注入）`);
    } else {
        const cleanCsvCell = (val) => {
            const safeVal = sanitizeSpreadsheetCell(val);
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
    const eligibleLeads = leads.filter(l => hasReplacementAuthority(l) && checkBrandCompatibility(l, customBrandProfile).compatible);
    if (eligibleLeads.length === 0) {
        showToast('当前筛选线索均因「跨赛道不匹配」或「无选型决策权」被拦截，请先切换匹配的卖方预设', true);
        return;
    }
    const skippedCount = leads.length - eligibleLeads.length;
    const fullText = eligibleLeads.map(l =>
        `【#${l.idx} 标的：${l.competitor} | 发帖人：@${l.author} | 来源ID：${l.source_id}】\n` +
        `原帖链接：${l.url}\n` +
        `原文证据：“${l.evidence_quote}”\n` +
        `【💬 公开透明利益披露回复】：\n${getEffectivePitch(l, 'reply')}\n` +
        `【💻 1v1 技术核验草稿】：\n${getEffectivePitch(l, 'dev')}`
    ).join('\n\n========================================\n\n');

    const msg = skippedCount > 0
        ? `已复制 ${eligibleLeads.length} 条合规话术（自动跳过 ${skippedCount} 条不匹配/无决策权线索）`
        : `已复制当前筛选 ${eligibleLeads.length} 条透明披露话术！`;
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
    const cls = PROVENANCE_BADGE_CLASSES[src] || PROVENANCE_BADGE_CLASSES['未知'];
    return `
    <div class="p-2.5 rounded-lg bg-zinc-50/90 border border-zinc-200/80 flex flex-col justify-between gap-1">
        <div class="flex items-center justify-between gap-1">
            <span class="text-[11px] font-semibold text-zinc-500">${escapeHtml(label)}</span>
            <span class="px-1.5 py-0.2 rounded text-[10px] font-bold border ${cls}">[${escapeHtml(src)}]</span>
        </div>
        <div class="text-xs font-medium text-zinc-800 leading-snug">${escapeHtml(val)}</div>
    </div>`;
}

function getScoreBadgeHtml(lead) {
    if (!hasReplacementAuthority(lead)) {
        return `<span class="whitespace-nowrap inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-50 text-amber-800 border border-amber-300" title="发帖人明示无选型决策权"><span class="w-1.5 h-1.5 rounded-full bg-amber-500"></span>${lead.intent_score}分 · 无决策权</span>`;
    }
    if (lead.intent_score >= 85) {
        return `<span class="whitespace-nowrap inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200"><span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>${lead.intent_score}分 · 已核验评估</span>`;
    }
    if (lead.intent_score >= 80) {
        return `<span class="whitespace-nowrap inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-blue-50 text-blue-800 border border-blue-200"><span class="w-1.5 h-1.5 rounded-full bg-blue-500"></span>${lead.intent_score}分 · 可跟进评估</span>`;
    }
    return `<span class="whitespace-nowrap inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-zinc-100 text-zinc-700 border border-zinc-300"><span class="w-1.5 h-1.5 rounded-full bg-zinc-500"></span>${lead.intent_score}分 · 待核验资格</span>`;
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
        const compat = checkBrandCompatibility(lead, customBrandProfile);

        const compatBadge = (!compat.compatible)
            ? `<span class="whitespace-nowrap flex-shrink-0 inline-flex items-center px-1.5 py-0.2 rounded text-[10px] font-semibold bg-rose-50 text-rose-700 border border-rose-200">⛔ 跨赛道不匹配</span>`
            : (customBrandProfile && customBrandProfile.brand_name && hasReplacementAuthority(lead)
                ? `<span class="whitespace-nowrap flex-shrink-0 inline-flex items-center px-1.5 py-0.2 rounded text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">✅ 适配 ${escapeHtml(customBrandProfile.brand_name)}</span>`
                : '');

        const candText = (lead.candidate_alternatives && lead.candidate_alternatives.length > 0)
            ? `提及候选: ${lead.candidate_alternatives.slice(0, 3).join(', ')}`
            : '未点名特定候选';

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
                    <span class="text-[10px] text-zinc-500 font-medium">${escapeHtml(lead.qualification_stage.split('·')[0])}</span>
                </div>
            </td>
            <td class="py-2.5 px-2 whitespace-nowrap">
                <div class="flex flex-col gap-1 items-start">
                    <span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs font-semibold bg-zinc-100 text-zinc-800 border border-zinc-200/80">
                        ${logoHtml}
                        <span>${escapeHtml(lead.competitor)}</span>
                    </span>
                    <span class="text-[10px] text-zinc-500 truncate max-w-[155px]" title="${escapeHtml(candText)}">${escapeHtml(candText)}</span>
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
                <a href="${safeUrl}" target="_blank" rel="noopener noreferrer" class="inline-flex items-center px-2 py-1 rounded-md text-[11px] font-medium text-blue-700 bg-blue-50 hover:bg-blue-100 border border-blue-200 transition-colors" title="直接核验 Hacker News 原帖">
                    核验原帖 ↗
                </a>
                <button type="button" data-action="open-drawer" data-lead-id="${escapeHtml(lead.id)}" class="px-2 py-1 rounded-md text-[11px] font-semibold bg-zinc-900 text-white hover:bg-zinc-800 transition-colors shadow-xs">
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

        return `
        <div class="bg-white rounded-xl border border-zinc-200/90 p-4 shadow-xs hover:shadow-md transition-all cursor-pointer" data-action="open-drawer" data-lead-id="${escapeHtml(lead.id)}">
            <div class="flex flex-wrap items-center justify-between gap-2 pb-2.5 border-b border-zinc-100 mb-3" data-stop-propagation="true">
                <div class="flex items-center gap-2 flex-wrap">
                    <span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md text-xs font-bold bg-zinc-100 text-zinc-800 border border-zinc-200">
                        ${logoHtml}
                        <span>被替换标的：${escapeHtml(lead.competitor)}</span>
                    </span>
                    <span class="text-xs text-zinc-500 font-medium">${escapeHtml(lead.qualification_stage)}</span>
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
                    <a href="${safeUrl}" target="_blank" rel="noopener noreferrer" class="text-blue-600 hover:underline font-sans font-semibold">打开 HN 原帖 (#${escapeHtml(lead.source_id)}) ↗</a>
                </div>
                <div class="flex items-center gap-2">
                    <button type="button" data-action="copy-lead-pitch" data-lead-id="${escapeHtml(lead.id)}" class="px-2.5 py-1 rounded-lg text-xs font-medium text-zinc-700 bg-white hover:bg-zinc-100 border border-zinc-200">
                        复制透明披露回复
                    </button>
                    <button type="button" data-action="open-drawer" data-lead-id="${escapeHtml(lead.id)}" class="px-3 py-1 rounded-lg text-xs font-semibold bg-zinc-900 text-white hover:bg-zinc-800">
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
        const compat = checkBrandCompatibility(lead, customBrandProfile);

        const itemClass = isSelected
            ? 'w-full text-left p-3 bg-emerald-50/80 border-l-4 border-l-emerald-600 transition-all cursor-pointer focus:outline-none focus:ring-2 focus:ring-inset focus:ring-zinc-900'
            : 'w-full text-left p-3 hover:bg-zinc-50 transition-all cursor-pointer border-l-4 border-l-transparent focus:outline-none focus:ring-2 focus:ring-inset focus:ring-zinc-900';

        return `
        <button type="button"
                id="split-item-${escapeHtml(lead.id)}"
                data-action="select-split-lead"
                data-lead-id="${escapeHtml(lead.id)}"
                aria-selected="${isSelected ? 'true' : 'false'}"
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
                    ${!compat.compatible ? `<span class="text-rose-600 font-semibold">⛔不匹配</span>` : ''}
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
    const candList = (lead.candidate_alternatives && lead.candidate_alternatives.length > 0)
        ? lead.candidate_alternatives.join(' / ')
        : '原帖未点名特定候选产品';

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
        compBadgeEl.innerHTML = `${logoHtml} <span>被替换竞品：${escapeHtml(lead.competitor)}</span> <span class="text-zinc-400">|</span> <span class="text-zinc-600 font-normal">提及候选：${escapeHtml(candList)}</span>`;
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
        contactPathEl.innerText = qm.contact_path || '通过原帖公开透明披露开发者身份并提供迁移核验文档';
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
    const filtered = getFilteredAndSortedLeads();
    updateLiveCountsAndExportButtons(filtered);

    const tableWrap = document.getElementById('tableViewWrapper');
    const splitWrap = document.getElementById('splitViewWrapper');
    const cardWrap = document.getElementById('cardViewWrapper');

    if (tableWrap) tableWrap.classList.add('hidden');
    if (splitWrap) splitWrap.classList.add('hidden');
    if (cardWrap) cardWrap.classList.add('hidden');

    // Only render the active view (avoids redundant hidden DOM redraws)
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
// 7. Accessible Drawer, Focus Trap, Brand Capability Customizer & Event Delegation
// ============================================================================
function openDrawer(id, triggerEl = null) {
    const lead = LEADS_DATA.find(x => x.id === id);
    if (!lead) return;

    if (triggerEl || document.activeElement) {
        lastFocusedElement = triggerEl || document.activeElement;
    }

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
        requestAnimationFrame(() => {
            drawer.classList.remove('translate-x-full');
            const closeBtn = document.getElementById('drawerCloseBtn');
            if (closeBtn) closeBtn.focus();
        });
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
    activeLeadId = null;
    applyRender();
    if (lastFocusedElement && typeof lastFocusedElement.focus === 'function') {
        lastFocusedElement.focus();
        lastFocusedElement = null;
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
    const compInput = document.getElementById('customTargetCompetitors');
    const capInput = document.getElementById('customApprovedCaps');
    const limitInput = document.getElementById('customKnownLimits');
    const linkInput = document.getElementById('customBrandLink');

    if (nameInput) nameInput.value = preset.brand_name || '';
    if (compInput) compInput.value = (preset.target_competitors || ['*']).join(', ');
    if (capInput) capInput.value = preset.approved_capabilities || '';
    if (limitInput) limitInput.value = preset.known_limitations || '';
    if (linkInput) linkInput.value = preset.cta_link || '';
    applyCustomBrandProfile();
}

function applyCustomBrandProfile() {
    const nameVal = (document.getElementById('customBrandName')?.value || '').trim();
    const compRaw = (document.getElementById('customTargetCompetitors')?.value || '').trim();
    const capVal = (document.getElementById('customApprovedCaps')?.value || '').trim();
    const limitVal = (document.getElementById('customKnownLimits')?.value || '').trim();
    const linkVal = (document.getElementById('customBrandLink')?.value || '').trim();
    const indicator = document.getElementById('activeBrandIndicator');

    if (!nameVal) {
        customBrandProfile = null;
        if (indicator) {
            indicator.innerText = '当前视角：默认中立证据核验';
            indicator.className = 'text-[11px] font-medium text-zinc-600 bg-zinc-100 border border-zinc-200 px-2 py-0.5 rounded-md';
        }
        applyRender();
        if (activeLeadId) {
            populateDetailPane('drawer', activeLeadId);
            populateDetailPane('split', activeLeadId);
        }
        showToast('已切换为【默认中立证据核验视角】');
        return;
    }

    const parsedTargets = compRaw
        ? compRaw.split(/[,，/]/).map(s => s.trim()).filter(Boolean)
        : ['*'];

    customBrandProfile = {
        brand_name: nameVal,
        target_competitors: parsedTargets.length > 0 ? parsedTargets : ['*'],
        approved_capabilities: capVal || '支持标准数据导入与本地沙箱迁移验证',
        known_limitations: limitVal || '具体生产环境适配边界需结合贵司实际数据量级核实',
        cta_link: linkVal
    };

    if (indicator) {
        indicator.innerText = `已启用卖方能力门控：${nameVal} (仅适配 ${customBrandProfile.target_competitors.join('/')})`;
        indicator.className = 'text-[11px] font-semibold text-emerald-800 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-md';
    }

    applyRender();
    if (activeLeadId) {
        populateDetailPane('drawer', activeLeadId);
        populateDetailPane('split', activeLeadId);
    }
    showToast(`已启用【${nameVal}】能力边界门控（非匹配赛道将自动拦截话术生成）`);
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

function openHowItWorksModal(triggerEl = null) {
    lastFocusedElement = triggerEl || document.activeElement;
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
    if (lastFocusedElement && typeof lastFocusedElement.focus === 'function') {
        lastFocusedElement.focus();
        lastFocusedElement = null;
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

// Event Delegation for all dynamic lead rows/cards/buttons (Zero inline ID interpolation)
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
            copyToClipboard(getEffectivePitch(lead, 'reply'), `已复制 #${lead.idx} 透明披露话术`, actionEl);
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
    const isModalOpen = howItWorks && !howItWorks.classList.contains('hidden');
    const isDrawerOpen = drawer && !drawer.classList.contains('translate-x-full');

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

    if (!isEditable && !isModalOpen && !isDrawerOpen && currentViewMode === 'split') {
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
    Kept strictly separate from the public client-facing verification workbench (`report.html` / `index.html`).
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
        clients_html += f"""
        <div class="bg-white rounded-xl border border-zinc-200 p-5 shadow-xs space-y-3">
            <div class="flex items-start justify-between gap-2">
                <div>
                    <span class="text-xs font-mono font-bold text-zinc-500">#{idx} · 关联真实证据 ID: {_html.escape(client.get('verified_evidence_id', ''))}</span>
                    <h4 class="text-sm font-bold text-zinc-900">{_html.escape(client['name'])}</h4>
                    <p class="text-xs text-zinc-500">{_html.escape(client['category'])} · 阶段：{_html.escape(client['stage'])}</p>
                </div>
                <span class="px-2.5 py-0.5 rounded text-xs font-semibold bg-zinc-100 text-zinc-800 border border-zinc-200">
                    被替换竞品：{_html.escape(client['target_incumbent'])}
                </span>
            </div>
            <p class="text-xs text-zinc-700 bg-zinc-50 p-2.5 rounded-lg border border-zinc-200">
                <strong>匹配逻辑：</strong>{_html.escape(client['pain_point'])}
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
                🔒 内部运营后台文档 · 已与客户交付工作台 (report.html) 物理隔离
            </span>
            <span class="text-xs font-mono text-zinc-400">生成时间：{now_str}</span>
        </div>
        <h1 class="text-lg font-bold">IntentRadar · 诚实证据流 BD 与单赛道人工核验试点手册</h1>
        <p class="text-xs text-zinc-300 leading-relaxed">
            本页面仅供内部 BD 与运营使用，不在公开演示或客户交付页面展示。核心纪律：1) 每次只向目标卖方发送 1 条已核验真实原帖与原文摘录；2) 社区回复严格遵循「利益相关披露」原则，严禁伪装第三方过来人用户；3) 试点合作明确约定合格线索定义与未达标按条退款条款。
        </p>
    </header>

    <section class="space-y-3">
        <h2 class="text-base font-bold text-zinc-900">一、三档单赛道人工核验试点报价与退款兜底条款</h2>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
            {offers_html}
        </div>
    </section>

    <section class="space-y-3">
        <h2 class="text-base font-bold text-zinc-900">二、1对1 卖方开发名录（每家绑定 1 条已核验 HN 真实原帖证据）</h2>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            {clients_html}
        </div>
    </section>

    <section class="space-y-3">
        <h2 class="text-base font-bold text-zinc-900">三、透明利益披露社区回复模板与试点招募文案</h2>
        <div class="grid grid-cols-1 gap-4">
            {campaigns_html}
        </div>
    </section>
</body>
</html>"""
