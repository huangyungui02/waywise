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
  const userMessage = page.locator("article").getByText(prompt, { exact: true });
  const selection = await userMessage.evaluate((element) => {
    const range = document.createRange();
    range.selectNodeContents(element);
    const selected = window.getSelection()!;
    selected.removeAllRanges();
    selected.addRange(range);
    const style = getComputedStyle(element, "::selection");
    return { text: selected.toString(), color: style.color, background: style.backgroundColor };
  });
  expect(selection).toEqual({
    text: prompt,
    color: "rgb(25, 56, 46)",
    background: "rgb(217, 238, 227)",
  });
  await page.evaluate(() => window.getSelection()?.removeAllRanges());
  await expect(page.getByText("核对北京时间")).toBeVisible();
  await expect(page.getByRole("button", { name: /核对北京时间/ })).toHaveCount(0);
  await expect(page.getByText("2026-11-06 10:00", { exact: false })).toHaveCount(0);
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

test("表单合并发送，刷新恢复摘要，聊天调整需求和手机布局", async ({ page }) => {
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
  await expect(page.locator("article").first().getByText("上海", { exact: true })).toBeVisible();
  await expect(page.locator("article").first().getByText("杭州", { exact: true })).toBeVisible();
  await expect(page.getByLabel("出发城市", { exact: true })).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole("button", { name: "修改需求" })).toHaveCount(0);
  await expect(page.locator("article").first().getByText("杭州", { exact: true })).toBeVisible();
  await page.getByRole("textbox", { name: "旅行需求" }).fill("目的地改成苏州");
  await page.getByRole("button", { name: "发送", exact: true }).click();
  await expect(page.getByText("收到你的旅行想法：目的地改成苏州。")).toBeVisible();
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

test("连续工具记录自动滚动到底部且不提供结果详情", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("textbox", { name: "旅行需求" }).fill("工具滚动测试");
  await page.getByRole("button", { name: "开始规划" }).click();
  await expect(page.getByText(/收到你的旅行想法/)).toBeVisible();
  await page.route("**/api/conversations/*", async (route) => {
    const response = await route.fetch();
    const detail = await response.json();
    detail.messages = [{
      id: "tools-scroll",
      role: "assistant",
      parts: Array.from({ length: 20 }, (_, index) => ({
        type: "tool-current_time",
        toolCallId: `clock-${index}`,
        state: "output-available",
        input: {},
        output: "不应显示的工具原始结果",
      })),
    }];
    await route.fulfill({ response, json: detail });
  });
  await page.reload();
  const records = page.getByRole("region", { name: "行程查询记录" });
  await expect(records.getByText("核对北京时间")).toHaveCount(20);
  await expect.poll(() => records.evaluate((element) =>
    element.scrollHeight > element.clientHeight &&
    Math.abs(element.scrollHeight - element.clientHeight - element.scrollTop) < 2,
  )).toBe(true);
  await expect(records.getByRole("button")).toHaveCount(0);
  await expect(page.getByText("不应显示的工具原始结果")).toHaveCount(0);
});

for (const mobile of [false, true]) {
  test(`${mobile ? "手机" : "桌面"}聊天布局简化且回到底部按钮居中`, async ({ page }) => {
    await page.setViewportSize(mobile ? { width: 390, height: 844 } : { width: 1440, height: 900 });
    await page.goto("/");
    await page.getByRole("textbox", { name: "旅行需求" }).fill("布局测试");
    await page.getByRole("button", { name: "开始规划" }).click();
    await expect(page.getByText(/收到你的旅行想法/)).toBeVisible();
    await page.route("**/api/conversations/*", async (route) => {
      const response = await route.fetch();
      const detail = await response.json();
      detail.messages = [{
        id: "long-message",
        role: "assistant",
        parts: [{ type: "text", text: Array.from({ length: 50 }, (_, i) => `行程建议第 ${i + 1} 条。`).join("\n\n") }],
      }];
      await route.fulfill({ response, json: detail });
    });
    await page.reload();
    const article = page.locator("article").first();
    await expect(article).toContainText("行程建议第 50 条");
    expect(await article.evaluate((el) => el.children.length === 1 &&
      Math.abs(el.getBoundingClientRect().left - el.firstElementChild!.getBoundingClientRect().left) < 1,
    )).toBe(true);
    const scroller = article.locator("../..");
    await scroller.evaluate((el) => { el.scrollTop = 0; });
    const button = page.getByRole("button", { name: "回到最新消息" });
    await expect(button).toBeVisible();
    const buttonBox = (await button.boundingBox())!;
    const chatBox = (await scroller.boundingBox())!;
    expect(Math.abs(buttonBox.x + buttonBox.width / 2 - chatBox.x - chatBox.width / 2)).toBeLessThan(1);
    await button.click();
    await expect(button).toBeHidden();
    for (const text of ["知途 · 旅行手札", "山水有信 · 知途相伴", "基础安排 · 行囊", "确认方案不代表已经购买。请前往预订页面自行核对并支付。"]) {
      await expect(page.getByText(text, { exact: true })).toHaveCount(0);
    }
  });
}
