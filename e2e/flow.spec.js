const { test, expect } = require("@playwright/test");

test("데모 과원에서 일정 승인 후 작업을 기록한다", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "데모 과원 열기" }).click();
  await expect(page.locator("#today-content")).toContainText("수확 준비 점검");
  await expect(page.locator("#today-content")).toContainText("AI 생성");
  await expect(page.locator("#today-content")).toContainText("근거 있음");
  await page.getByLabel("물어볼 내용").fill("수확 준비 점검을 오늘 일정으로 잡아줘");
  await page.getByRole("button", { name: "보내기", exact: true }).click();
  await page.getByRole("button", { name: "승인하고 일정 추가" }).click();
  await expect(page.locator("#calendar-content")).toContainText("수확 준비 점검");
  await page.locator("#calendar summary").filter({ hasText: "작업·수확 기록" }).click();
  await page.getByLabel("기록 종류").selectOption("work");
  await page.getByLabel("작업·증상 메모").fill("수확 준비 점검");
  await page.getByRole("button", { name: "기록 저장" }).click();
  await expect(page.locator("#log-status")).toHaveText("기록을 저장했습니다.");
  await expect(page.locator("#log-content")).toContainText("수확 준비 점검");
  await expect(page.locator("#log-content")).toContainText("작업 완료");
});
