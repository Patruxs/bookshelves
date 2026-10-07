import { chromium, devices } from "playwright";
const base = "http://localhost:4173/bookshelves";
const browser = await chromium.launch({ executablePath: "/home/pat/.cache/ms-playwright/chromium_headless_shell-1234/chrome-headless-shell-linux64/chrome-headless-shell" });
const ctx = await browser.newContext({ ...devices["iPhone 13"], colorScheme: "light" });
const page = await ctx.newPage();
const shots = [
  ["home", "/home"],
  ["browse", "/browse"],
  ["browse-cat", "/browse?category=Computer%20Science%20Fundamentals"],
  ["browse-list", "/browse?category=Computer%20Science%20Fundamentals&topic=Data%20Structures%20and%20Algorithms"],
];
for (const [name, path] of shots) {
  await page.goto(base + path, { waitUntil: "networkidle" });
  await page.waitForTimeout(800);
  await page.screenshot({ path: `/tmp/mobshots/${name}.png`, fullPage: true });
  await page.screenshot({ path: `/tmp/mobshots/${name}-fold.png` });
}
const id = await page.evaluate(async () => { const d = await (await fetch("/bookshelves/data.json")).json(); const b = Array.isArray(d) ? d : d.books; return b[3].id; });
await page.goto(`${base}/book/${id}`, { waitUntil: "networkidle" });
await page.waitForTimeout(800);
await page.screenshot({ path: `/tmp/mobshots/book.png`, fullPage: true });
await page.goto(base + "/browse?category=Computer%20Science%20Fundamentals", { waitUntil: "networkidle" });
await page.getByRole("button", { name: /Topics/ }).first().click();
await page.waitForTimeout(600);
await page.screenshot({ path: `/tmp/mobshots/topics-sheet.png` });
await page.keyboard.press("Escape");
await page.getByRole("button", { name: "Search" }).first().click();
await page.waitForTimeout(600);
await page.screenshot({ path: `/tmp/mobshots/search.png` });
await browser.close();
