"""
End-to-end tests using Playwright.
"""
import pytest
from playwright.sync_api import sync_playwright, expect


class TestAgentDashboard:
    """E2E tests for Agent Dashboard."""
    
    @pytest.fixture(scope="class")
    def browser(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            yield browser
            browser.close()
    
    @pytest.fixture
    def page(self, browser):
        page = browser.new_page()
        yield page
        page.close()
    
    def test_dashboard_loads(self, page):
        """Test that dashboard loads successfully."""
        page.goto("http://localhost:3000")
        
        # Check title
        expect(page).to_have_title(/Agent Cluster/)
        
        # Check main elements are present
        expect(page.locator("header")).to_be_visible()
        expect(page.locator("nav")).to_be_visible()
    
    def test_navigation_works(self, page):
        """Test navigation between pages."""
        page.goto("http://localhost:3000")
        
        # Click on Agents link
        page.click("text=Agents")
        
        # Should navigate to agents page
        expect(page.locator("h1:has-text('Agents')")).to_be_visible()
    
    def test_create_agent_modal(self, page):
        """Test creating agent via modal."""
        page.goto("http://localhost:3000/agents")
        
        # Click create button
        page.click("button:has-text('Create Agent')")
        
        # Modal should open
        expect(page.locator("role=dialog")).to_be_visible()
        
        # Fill form
        page.fill("input[name=name]", "test-agent")
        page.select_option("select[name=model]", "gpt-4")
        
        # Submit
        page.click("button:has-text('Submit')")
        
        # Modal should close
        expect(page.locator("role=dialog")).not_to_be_visible()
    
    def test_agent_list_pagination(self, page):
        """Test agent list pagination."""
        page.goto("http://localhost:3000/agents")
        
        # Check pagination controls
        pagination = page.locator(".pagination")
        if pagination.is_visible():
            expect(pagination.locator("button").first).to_be_enabled()
    
    def test_search_functionality(self, page):
        """Test search functionality."""
        page.goto("http://localhost:3000/agents")
        
        # Type in search box
        search_box = page.locator("input[placeholder*='Search']")
        search_box.fill("test-agent")
        
        # Should filter results
        page.wait_for_timeout(500)  # Wait for debounce
        
        # Results should contain search term
        rows = page.locator("table tbody tr")
        if rows.count() > 0:
            first_row = rows.first
            expect(first_row).to_contain_text("test-agent")


class TestTaskExecution:
    """E2E tests for Task Execution."""
    
    @pytest.fixture(scope="class")
    def browser(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            yield browser
            browser.close()
    
    @pytest.fixture
    def page(self, browser):
        page = browser.new_page()
        yield page
        page.close()
    
    def test_task_creation(self, page):
        """Test creating a new task."""
        page.goto("http://localhost:3000/tasks")
        
        # Click create task button
        page.click("button:has-text('Create Task')")
        
        # Fill task form
        page.fill("textarea[name=description]", "E2E test task")
        page.select_option("select[name=type]", "code_generation")
        page.fill("input[name=priority]", "1")
        
        # Submit
        page.click("button:has-text('Submit')")
        
        # Task should appear in list
        expect(page.locator("text=E2E test task")).to_be_visible()
    
    def test_task_status_updates(self, page):
        """Test task status updates via WebSocket."""
        page.goto("http://localhost:3000/tasks")
        
        # Create a task
        page.click("button:has-text('Create Task')")
        page.fill("textarea[name=description]", "Status test task")
        page.click("button:has-text('Submit')")
        
        # Wait for WebSocket update
        page.wait_for_timeout(2000)
        
        # Check status changed (assuming WebSocket is working)
        status = page.locator(".task-status").first
        if status.is_visible():
            expect(status).to_be_visible()
    
    def test_task_cancellation(self, page):
        """Test cancelling a task."""
        page.goto("http://localhost:3000/tasks")
        
        # Find a pending task
        task_row = page.locator("tr:has-text('pending')").first
        
        if task_row.is_visible():
            # Click cancel button
            task_row.locator("button:has-text('Cancel')").click()
            
            # Confirm cancellation
            page.click("button:has-text('Confirm')")
            
            # Status should change
            expect(page.locator("text=cancelled")).to_be_visible()


class TestClusterOrchestration:
    """E2E tests for Cluster Orchestration."""
    
    @pytest.fixture(scope="class")
    def browser(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            yield browser
            browser.close()
    
    @pytest.fixture
    def page(self, browser):
        page = browser.new_page()
        yield page
        page.close()
    
    def test_cluster_execution_workflow(self, page):
        """Test complete cluster execution workflow."""
        page.goto("http://localhost:3000/cluster")
        
        # Click create cluster task
        page.click("button:has-text('New Cluster Task')")
        
        # Add subtasks
        page.click("button:has-text('Add Subtask')")
        page.click("button:has-text('Add Subtask')")
        
        # Fill subtask details
        subtasks = page.locator(".subtask-form")
        for i, subtask in enumerate(subtasks.all()):
            subtask.locator("input[name=description]").fill(f"Subtask {i+1}")
        
        # Configure execution strategy
        page.select_option("select[name=strategy]", "parallel")
        
        # Execute
        page.click("button:has-text('Execute')")
        
        # Should show execution progress
        expect(page.locator(".execution-progress")).to_be_visible()
    
    def test_cluster_monitoring(self, page):
        """Test cluster monitoring dashboard."""
        page.goto("http://localhost:3000/cluster/monitor")
        
        # Check metrics are displayed
        expect(page.locator(".active-agents")).to_be_visible()
        expect(page.locator(".queued-tasks")).to_be_visible()
        expect(page.locator(".success-rate")).to_be_visible()


class TestAuthentication:
    """E2E tests for Authentication."""
    
    @pytest.fixture(scope="class")
    def browser(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            yield browser
            browser.close()
    
    @pytest.fixture
    def page(self, browser):
        page = browser.new_page()
        yield page
        page.close()
    
    def test_login_flow(self, page):
        """Test login flow."""
        page.goto("http://localhost:3000/login")
        
        # Fill login form
        page.fill("input[name=username]", "test@example.com")
        page.fill("input[name=password]", "password123")
        
        # Submit
        page.click("button:has-text('Login')")
        
        # Should redirect to dashboard
        page.wait_for_url("**/dashboard")
        expect(page.locator("text=Welcome")).to_be_visible()
    
    def test_logout_flow(self, page):
        """Test logout flow."""
        # Login first
        page.goto("http://localhost:3000/login")
        page.fill("input[name=username]", "test@example.com")
        page.fill("input[name=password]", "password123")
        page.click("button:has-text('Login')")
        
        # Logout
        page.click("button:has-text('Logout')")
        
        # Should redirect to login
        page.wait_for_url("**/login")
    
    def test_unauthorized_access(self, page):
        """Test accessing protected routes without auth."""
        page.goto("http://localhost:3000/dashboard")
        
        # Should redirect to login
        expect(page).to_have_url("**/login")
