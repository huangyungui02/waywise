import { expect, test } from "@playwright/test";

test("新建、发送、工具展示、刷新恢复、切换与删除", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await page.screenshot({
    path: "/private/tmp/travel-agent-welcome.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "开始一段旅行" }).click();
  await expect(page).toHaveURL(/\/chat\//);
  const firstUrl = page.url();
  const prompt = `去杭州 ${Date.now()}`;
  await page.getByRole("textbox", { name: "旅行需求" }).fill(prompt);
  await page.getByRole("button", { name: /^(发送|开始规划)$/ }).click();
  await expect(page.getByText(`收到你的旅行想法：${prompt}。`)).toBeVisible();
  await expect(page.getByText("核对北京时间")).toBeVisible();
  await page.getByRole("button", { name: /核对北京时间/ }).click();
  await expect(
    page.getByText("2026-11-06 10:00", { exact: false }),
  ).toBeVisible();
  await page.getByRole("button", { name: /核对北京时间/ }).click();
  await page.reload();
  await expect(page.getByText(`收到你的旅行想法：${prompt}。`)).toBeVisible();
  await page.getByRole("button", { name: "开始一段旅行" }).click();
  await expect(
    page.getByRole("textbox", { name: "旅行需求" }),
  ).toBeVisible();
  await page.getByRole("link", { name: new RegExp(prompt) }).click();
  await expect(page).toHaveURL(firstUrl);
  await expect(page.getByText(`收到你的旅行想法：${prompt}。`)).toBeVisible();
  await page.screenshot({
    path: "/private/tmp/travel-agent-desktop.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: `删除 ${prompt}` }).click();
  await expect(page.getByRole("alertdialog")).toBeVisible();
  await page.getByRole("button", { name: "确认删除", exact: true }).click();
  await expect(page).toHaveURL("http://127.0.0.1:5179/");
  expect(errors).toEqual([]);
});

test("手机界面可输入、发送和读取历史，页面没有横向溢出", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.getByRole("textbox", { name: "旅行需求" }).fill("开始旅行");
  await page.getByRole("button", { name: "开始规划" }).click();
  await expect(page.getByText(/收到你的旅行想法/)).toBeVisible();
  await page.getByRole("textbox", { name: "旅行需求" }).fill("我想去重庆");
  await page.getByRole("button", { name: /^(发送|开始规划)$/ }).click();
  await expect(page.getByText("收到你的旅行想法：我想去重庆。")).toBeVisible();
  await page.reload();
  await expect(page.getByText("收到你的旅行想法：我想去重庆。")).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "/private/tmp/travel-agent-mobile.png",
    fullPage: true,
  });
});

test("停止生成后仍能读取已保存记录并继续聊天", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("textbox", { name: "旅行需求" }).fill("开始旅行");
  await page.getByRole("button", { name: "开始规划" }).click();
  await expect(page.getByText(/收到你的旅行想法/)).toBeVisible();
  await page.getByRole("textbox", { name: "旅行需求" }).fill("停止测试");
  await page.getByRole("button", { name: /^(发送|开始规划)$/ }).click();
  await expect(page.getByText("正在安排这次旅行…")).toBeVisible();
  await page.getByRole("button", { name: "停止" }).click();
  await page.reload();
  await expect(
    page.getByText("停止测试", { exact: true }).last(),
  ).toBeVisible();
  await page.getByRole("textbox", { name: "旅行需求" }).fill("继续聊杭州");
  await page.getByRole("button", { name: /^(发送|开始规划)$/ }).click();
  await expect(page.getByText("收到你的旅行想法：继续聊杭州。")).toBeVisible();
});

test("表单合并发送，刷新恢复摘要，修改需求和手机布局", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.getByLabel("出发城市", { exact: true }).fill("上海");
  await page.getByLabel("目的城市", { exact: true }).fill("杭州");
  await page.getByLabel("出发日期", { exact: true }).fill("2026-12-01");
  await page.getByLabel("返回日期", { exact: true }).fill("2026-12-03");
  await page.getByLabel("成人", { exact: true }).fill("2");
  await page.getByRole("button", { name: "慢节奏", exact: true }).click();
  await page.getByRole("textbox", { name: "旅行需求" }).fill("想住湖边");
  await page.getByRole("button", { name: "开始规划" }).click();
  await expect(page.getByText(/收到你的旅行想法/)).toBeVisible();
  await expect(page.getByText(/上海 → 杭州/)).toBeVisible();
  await expect(page.getByLabel("出发城市", { exact: true })).toHaveCount(0);
  await page.reload();
  await page.getByRole("button", { name: "修改需求" }).click();
  await expect(page.getByLabel("目的城市", { exact: true })).toHaveValue("杭州");
  await expect(page.getByRole("button", { name: "慢节奏", exact: true })).toHaveAttribute("aria-pressed", "true");
  await page.getByLabel("目的城市", { exact: true }).fill("苏州");
  await page.getByRole("button", { name: "发送修改" }).click();
  await expect(page.getByText(/上海 → 苏州/)).toBeVisible();
  await page.getByRole("button", { name: "旅行安排", exact: true }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: "/private/tmp/travel-agent-mobile.png", fullPage: true });
});

for (const mobile of [false, true]) {
  test(`${mobile ? "手机" : "桌面"}展示已确认的交通、酒店和购买状态`, async ({
    page,
  }) => {
    if (mobile) await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/");
    await page.getByRole("textbox", { name: "旅行需求" }).fill("开始旅行");
  await page.getByRole("button", { name: "开始规划" }).click();
  await expect(page.getByText(/收到你的旅行想法/)).toBeVisible();
    await expect(page).toHaveURL(/\/chat\//);
    const leg = {
      type: "train",
      number: "G123",
      departure_station: "上海虹桥",
      arrival_station: "杭州东",
      departure_time: "2026-12-01T09:00:00",
      arrival_time: "2026-12-01T10:00:00",
      purchased: true,
      purchase_url: null,
    };
    await page.route("**/api/conversations/*", async (route) => {
      const response = await route.fetch();
      const detail = await response.json();
      detail.trip = {
        outbound: leg,
        inbound: {
          ...leg,
          number: "G456",
          departure_station: "杭州东",
          arrival_station: "上海虹桥",
          purchased: false,
          purchase_url: "https://example.com/train",
        },
        stays: [
          {
            hotel: "杭州测试酒店",
            address: "西湖区测试路 1 号",
            check_in: "2026-12-01",
            check_out: "2026-12-03",
            booked: false,
            purchase_url: "https://example.com/hotel",
          },
        ],
      };
      await route.fulfill({ response, json: detail });
    });
    await page.reload();
    if (mobile) await page.getByRole("button", { name: "旅行安排" }).click();
    const panel = mobile
      ? page.getByRole("dialog")
      : page.getByRole("complementary", { name: "旅行基础安排" });
    await expect(panel.getByText("已确认方案")).toBeVisible();
    await expect(panel.getByText("G123", { exact: true })).toBeVisible();
    await expect(panel.getByText("已购买", { exact: true })).toBeVisible();
    await expect(panel.getByRole("link", { name: "前往购买" })).toHaveAttribute(
      "href",
      "https://example.com/train",
    );
    await expect(panel.getByText("杭州测试酒店")).toBeVisible();
    await expect(panel.getByRole("link", { name: "前往预订" })).toHaveAttribute(
      "href",
      "https://example.com/hotel",
    );
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
  });
}
