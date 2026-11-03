const { test, expect } = require('@playwright/test');

test.beforeEach(async ({ page }) => { await page.goto('/index.html'); });

test('drawer keeps focus, ignores background search shortcut, and restores trigger', async ({ page }) => {
  const trigger = page.locator('#drawer-trigger-hn_36042152');
  await trigger.focus();
  await trigger.press('Enter');
  const close = page.locator('#drawerCloseBtn');
  await expect(close).toBeFocused();
  await close.press('/');
  await expect(close).toBeFocused();
  await close.press('Escape');
  await expect(trigger).toBeFocused();
  await expect(page.locator('#detailDrawer')).toHaveAttribute('inert', '');
});

test('zero results disables scoped exports and never expands into all data', async ({ page }) => {
  await page.locator('#searchInput').fill('__no_matching_audit__');
  await expect(page.locator('#btnExportFilteredXlsx')).toBeDisabled();
  await expect(page.locator('#btnExportFilteredCsv')).toBeDisabled();
  await expect(page.locator('#btnExportAllXlsx')).toBeEnabled();
});

test('historical fit review reaches stage 3 only; changing seller invalidates it', async ({ page }) => {
  await page.locator('#btnToggleCustomizer').click();
  await page.getByRole('button', { name: /敏捷研发协同/ }).click();
  await page.locator('#drawer-trigger-hn_27018935').click();
  await expect(page.locator('#drawerScoreBadge')).toContainText('阶段 2/4');
  await page.locator('#drawerReviewer').fill('CI reviewer');
  await page.locator('#drawerFit').selectOption('supported');
  await page.locator('#drawerReviewEvidence').fill('已逐项核对原帖工作流与产品文档；这是历史核验演练。');
  await page.locator('#detailDrawer').getByRole('button', { name: '保存本条核验' }).click();
  await expect(page.locator('#drawerScoreBadge')).toContainText('阶段 3/4');
  await expect(page.locator('#drawerPitch')).toContainText('仅作中立核验');
  await page.locator('#drawerCloseBtn').press('Escape');
  await page.locator('#customApprovedCaps').fill('已修改的能力');
  await page.getByRole('button', { name: '应用门控', exact: true }).click();
  await page.locator('#drawer-trigger-hn_27018935').click();
  await expect(page.locator('#drawerScoreBadge')).toContainText('阶段 2/4');
});

test('storage quota error preserves the new session status', async ({ page }) => {
  // Set the failure before page initialization, without relying on app globals.
  await page.addInitScript(() => {
    Storage.prototype.setItem = () => { throw new DOMException('quota', 'QuotaExceededError'); };
  });
  await page.reload();
  await page.locator('#drawer-trigger-hn_36042152').click();
  await page.locator('#drawerStatusSelect').selectOption('已触达');
  await expect(page.locator('#drawerStatusSelect')).toHaveValue('已触达');
});
