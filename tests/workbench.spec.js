const { test, expect } = require('@playwright/test');

// Helper to open workbench with guide already seen to test core workflows without modal blocking
async function gotoWorkbench(page) {
  await page.addInitScript(() => {
    localStorage.setItem('ir_guide_seen', '1');
  });
  await page.goto('/index.html');
}

test('1. First load opens guide modal; Esc closes it; reload does not pop up', async ({ page }) => {
  await page.goto('/index.html');

  const guide = page.locator('#guide');
  await expect(guide).toBeVisible();

  // Press Esc to dismiss the modal
  await page.keyboard.press('Escape');
  await expect(guide).toBeHidden();

  // Reload the page and ensure guide is not shown again
  await page.reload();
  await expect(guide).toBeHidden();
});

test('2. J and K switch selected lead and right detail title updates', async ({ page }) => {
  await gotoWorkbench(page);

  const detailTitle = page.locator('#detailTitle');
  const initialTitle = await detailTitle.textContent();

  // Press J to move to the next lead
  await page.keyboard.press('j');
  const secondTitle = await detailTitle.textContent();
  expect(secondTitle).not.toBe(initialTitle);

  // Press K to move back to the previous lead
  await page.keyboard.press('k');
  const revertedTitle = await detailTitle.textContent();
  expect(revertedTitle).toBe(initialTitle);
});

test('3. Enter opens review drawer; Esc closes and restores focus to trigger', async ({ page }) => {
  await gotoWorkbench(page);

  const firstLead = page.locator('#leads .lead').first();
  await firstLead.focus();
  await page.keyboard.press('Enter');

  const drawer = page.locator('#drawer');
  await expect(drawer).toBeVisible();

  // Esc closes drawer and restores focus
  await page.keyboard.press('Escape');
  await expect(drawer).toBeHidden();
  await expect(firstLead).toBeFocused();
});

test('4. Slash focuses search; slash does not focus search when drawer is open', async ({ page }) => {
  await gotoWorkbench(page);

  const searchInput = page.locator('#search');
  await page.keyboard.press('/');
  await expect(searchInput).toBeFocused();

  // Unfocus search
  await page.keyboard.press('Escape');
  await expect(searchInput).not.toBeFocused();

  // Open drawer
  const firstLead = page.locator('#leads .lead').first();
  await firstLead.focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('#drawer')).toBeVisible();

  // Pressing / while drawer is open should NOT focus search
  await page.keyboard.press('/');
  await expect(searchInput).not.toBeFocused();
});

test('5. Checking 2 leads shows batch bar; batch reject moves them to blocked tab', async ({ page }) => {
  await gotoWorkbench(page);

  const checkboxes = page.locator('#leads .lead-check input[type="checkbox"]');
  await checkboxes.nth(0).check();
  await checkboxes.nth(1).check();

  const batchBar = page.locator('#batchBar');
  await expect(batchBar).toBeVisible();
  await expect(batchBar).toContainText('已选中 2 条线索');

  // Click batch reject button
  await batchBar.getByRole('button', { name: '批量拦截' }).click();

  // Confirm batch rejection
  const confirmBtn = page.locator('#batchConfirmBtn');
  await expect(confirmBtn).toBeVisible();
  await confirmBtn.click();

  // Switch to blocked tab and verify presence of both rejected leads
  const blockedTab = page.locator('#tabs button', { hasText: '已拦截' });
  await blockedTab.click();

  await expect(page.locator('#leads .lead[data-id="hn_41648918"]')).toBeVisible();
  await expect(page.locator('#leads .lead[data-id="hn_27018935"]')).toBeVisible();
});

test('6. In 375x812 viewport drawer slides up from bottom with button height >= 44px', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await gotoWorkbench(page);

  // In mobile view, clicking a lead opens detail view
  await page.locator('#leads .lead').first().click();

  // Click start review button
  const startReviewBtn = page.getByRole('button', { name: '开始能力核验' });
  await expect(startReviewBtn).toBeVisible();
  await startReviewBtn.click();

  const drawer = page.locator('#drawer');
  await expect(drawer).toBeVisible();

  const drawerBox = await drawer.boundingBox();
  expect(drawerBox).not.toBeNull();
  // Bottom of drawer aligns near bottom of screen
  expect(drawerBox.y + drawerBox.height).toBeGreaterThanOrEqual(800);

  // Check 3-state segment buttons height >= 44px
  const segButtons = drawer.locator('.seg button');
  const count = await segButtons.count();
  expect(count).toBeGreaterThan(0);
  for (let i = 0; i < count; i++) {
    const box = await segButtons.nth(i).boundingBox();
    expect(box.height).toBeGreaterThanOrEqual(44);
  }
});

test('7. Injected lead with title <img src=x onerror=alert(1)> displays as plain text without alert', async ({ page }) => {
  let alertTriggered = false;
  page.on('dialog', async (dialog) => {
    alertTriggered = true;
    await dialog.dismiss();
  });

  await gotoWorkbench(page);

  await page.evaluate(() => {
    window.LEADS.unshift({
      id: 'xss_attack_test',
      comp: 'MaliciousApp',
      title: '<img src=x onerror=alert(1)>',
      author: 'hacker',
      date: '2024-11-03',
      replies: 0,
      stage: 1,
      quote: '<script>alert(2)</script>',
      facts: [],
      todos: [],
      reqs: [],
      reply: 'test payload'
    });
    window.state.sel = 'xss_attack_test';
    window.render();
  });

  await page.waitForTimeout(300);

  const detailTitle = page.locator('#detailTitle');
  await expect(detailTitle).toHaveText('<img src=x onerror=alert(1)>');
  expect(await detailTitle.locator('img').count()).toBe(0);
  expect(alertTriggered).toBe(false);
});

test('8. Exported CSV prefixes cells starting with = with apostrophe', async ({ page }) => {
  await gotoWorkbench(page);

  const escaped = await page.evaluate(() => {
    return {
      equal: window.csvCell('=1+1'),
      plus: window.csvCell('+123'),
      minus: window.csvCell('-123'),
      at: window.csvCell('@cmd'),
      tab: window.csvCell('\ttext'),
      normal: window.csvCell('normal text')
    };
  });

  expect(escaped.equal).toBe("\"'=1+1\"");
  expect(escaped.plus).toBe("\"'+123\"");
  expect(escaped.minus).toBe("\"'-123\"");
  expect(escaped.at).toBe("\"'@cmd\"");
  expect(escaped.tab).toBe("\"'\ttext\"");
  expect(escaped.normal).toBe('"normal text"');

  // Verify CSV export content escaping formula
  await page.evaluate(() => {
    window.LEADS[0].title = '=SUM(1,2)';
    window.render();
  });

  const downloadPromise = page.waitForEvent('download');
  await page.locator('#exportBtn').click();
  await page.locator('#exportMenu button[data-export="csv-view"]').click();
  const download = await downloadPromise;
  const stream = await download.createReadStream();
  const chunks = [];
  for await (const chunk of stream) {
    chunks.push(chunk);
  }
  const content = Buffer.concat(chunks).toString('utf-8');
  expect(content).toContain("\"'=SUM(1,2)\"");
});
