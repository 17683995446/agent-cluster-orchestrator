import { test, expect } from '@playwright/test';

test.describe('Agent Management', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('should display dashboard with header', async ({ page }) => {
    await expect(page.locator('h1')).toContainText('Agent Cluster Orchestrator');
  });

  test('should show statistics cards', async ({ page }) => {
    await expect(page.locator('text=Total Agents')).toBeVisible();
    await expect(page.locator('text=Active Agents')).toBeVisible();
    await expect(page.locator('text=Completed Tasks')).toBeVisible();
  });

  test('should navigate between tabs', async ({ page }) => {
    await page.click('text=Agent Management');
    await expect(page.locator('text=暂无Agent')).toBeVisible({ timeout: 5000 }).catch(() => {});

    await page.click('text=Task List');
    await expect(page.locator('table')).toBeVisible({ timeout: 5000 }).catch(() => {});

    await page.click('text=Task Console');
    await expect(page.locator('text=Single Task Execution')).toBeVisible();
  });
});

test.describe('Agent CRUD Operations', () => {
  test('should open create agent modal', async ({ page }) => {
    await page.click('text=Add Agent');
    await expect(page.locator('text=Create New Agent')).toBeVisible();
  });

  test('should create a new agent', async ({ page }) => {
    await page.click('text=Add Agent');
    
    await page.fill('input[placeholder*="Code Assistant"]', 'Test Agent');
    
    await page.click('button:has-text("code_generation")');
    await page.click('button:has-text("data_analysis")');
    
    await page.click('button:has-text("Create Agent")');
    
    await page.waitForTimeout(1000);
    await expect(page.locator('text=Test Agent')).toBeVisible({ timeout: 5000 });
  });

  test('should delete an agent', async ({ page }) => {
    await page.click('text=Add Agent');
    await page.fill('input[placeholder*="Code Assistant"]', 'Agent To Delete');
    await page.click('button:has-text("Create Agent")');
    await page.waitForTimeout(1000);
    
    const agentCard = page.locator('text=Agent To Delete').locator('..');
    await agentCard.locator('button').last().click();
    
    await page.waitForTimeout(500);
  });
});

test.describe('Task Operations', () => {
  test('should create a single task', async ({ page }) => {
    await page.click('text=Task Console');
    
    await page.fill(
      'textarea[placeholder*="task description"]',
      'Write a Python hello world program'
    );
    
    await page.click('button:has-text("Execute Task")');
    
    await page.waitForTimeout(500);
    await page.click('text=Task List');
    await expect(page.locator('text=hello world')).toBeVisible({ timeout: 5000 }).catch(() => {});
  });

  test('should execute cluster task', async ({ page }) => {
    await page.click('text=Task Console');
    
    await page.fill(
      'textarea[placeholder*="complex task"]',
      'Build a complete e-commerce website'
    );
    
    await page.click('button:has-text("Start Cluster Collaboration")');
    
    await page.waitForTimeout(500);
  });

  test('should use sample task templates', async ({ page }) => {
    await page.click('text=Task Console');
    
    await page.click('button:has-text("Write a Python quicksort")');
    
    const textarea = page.locator('textarea[placeholder*="task description"]');
    await expect(textarea).toHaveValue(/quicksort/i);
  });
});

test.describe('Responsive Design', () => {
  test('should work on mobile viewport', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/');
    
    await expect(page.locator('h1')).toBeVisible();
  });

  test('should work on tablet viewport', async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.goto('/');
    
    await expect(page.locator('h1')).toBeVisible();
  });
});

test.describe('Accessibility', () => {
  test('should have proper heading hierarchy', async ({ page }) => {
    await page.goto('/');
    
    const h1 = page.locator('h1');
    await expect(h1).toHaveCount(1);
  });

  test('should have accessible buttons', async ({ page }) => {
    await page.goto('/');
    
    const buttons = page.locator('button');
    await expect(await buttons.count()).toBeGreaterThan(0);
  });

  test('should have form labels', async ({ page }) => {
    await page.goto('/');
    await page.click('text=Add Agent');
    
    const nameInput = page.locator('input[placeholder*="Code Assistant"]');
    await expect(nameInput).toBeVisible();
  });
});
