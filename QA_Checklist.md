# 🧪 PingBot QA Testing Guide

This document provides a step-by-step manual testing plan for all `PingBot` features. Go through these steps to ensure bot stability after refactoring or adding new features.

## 1. Basic Commands & Main Menu
- [ ] Send `/start`. Verify the welcome message and the persistent bottom-bar keyboard appear.
- [ ] Send `/help`. Verify the help text is correct and nicely formatted.
- [ ] Send `/about`. Verify the bot version and description are displayed.
- [ ] Tap the "⚙️ Налаштування" button on the persistent keyboard. Verify it opens the settings menu.
- [ ] Tap the "🗑️ Видалити адресу" button on the persistent keyboard. Verify it opens the delete list.

## 2. Add Host Flow
- [ ] Send `/add` or tap "➕ Додати адресу".
- [ ] Enter an **invalid** address (e.g., `12345` or `invalid_ip`). Verify the bot rejects it with a hint.
- [ ] Enter a **valid** IPv4 address (e.g., `8.8.8.8`).
- [ ] Enter a **name** for the host (e.g., `Google DNS`).
- [ ] The bot will ask for sensitivity. Tap "⏭️ Пропустити" (Skip).
- [ ] Verify the success message appears.
- [ ] Try adding another host. During the flow, tap "❌ Скасувати". Verify the process is aborted and the main menu is restored.
- [ ] Try adding a **cluster** of hosts (e.g., `8.8.8.8, 1.1.1.1`).

## 3. Host Management (List & Edit Flow)
- [ ] Send `/list` or tap "📋 Мій список".
- [ ] Verify the host list appears with current statuses (🟢/🔴) and inline buttons.
- [ ] Tap "🔍 Перевірити" (Check) under a host. The bot should return its current status.
- [ ] Tap "⏸ Пауза". The list status should change to "(ПАУЗА)" and the button to "▶️ Продовжити". Tap again to resume.
- [ ] Tap "✏️ Назва". Enter a new name. Verify the name is updated.
- [ ] Tap "✏️ Адреса/Кластер". Change the address (e.g., `1.1.1.1`). Verify it is saved.
- [ ] Tap "⚙️ Чутливість". Enter `3`. Verify the update. Repeat and enter `0` to reset to the default threshold.
- [ ] Tap "🗑️ Видалити". Tap "↩️ Назад" (Cancel) to abort.
- [ ] Tap "🗑️ Видалити" and confirm with "✅ Так, видалити". Verify the host is removed.

## 4. Chat Settings Menu
- [ ] Send `/settings` (or tap the bottom menu button). Verify the inline settings menu appears.
- [ ] Tap "📊 Звіти: Увімкнено". Verify the text changes to "Вимкнено" and vice versa.
- [ ] Tap "🙈 Порожні щоденні: Надсилати". Verify it changes to "Пропускати".
- [ ] Tap "🕒 Час звітів". Enter an invalid time (`99:99`). Verify validation fails. Enter `15:30`. Verify it updates in the menu.
- [ ] Tap "🌍 Часовий пояс". Enter an invalid timezone (`Kyiv/Europe`). The bot should reject it. Enter `Europe/Warsaw`. Verify it is saved.
- [ ] Tap "🌙 Тихі години". Enter `23:00-07:00`. Verify it updates in the menu.
- [ ] Tap "✅ Готово". The menu should close/disappear.

## 5. Background Monitoring & Quiet Hours
- [ ] Add a deliberately unreachable IP (e.g., `192.0.2.1`) with a sensitivity of `1`. 
- [ ] Wait for 1-2 minutes. Verify the bot sends a "🔴 Втрачено зв'язок" (Connection lost) alert.
- [ ] Set "Quiet Hours" in `/settings` to cover the current time. 
- [ ] Change the unreachable IP to a reachable one (e.g., `8.8.8.8`). 
- [ ] Wait for 1-2 minutes. Verify the bot **does NOT** send a recovery alert immediately due to Quiet Hours.

## 6. Spam Protection & Access Control
- [ ] Invite the bot to a Group Chat.
- [ ] As a **non-admin** user, try sending `/add`, `/delete`, or `/settings`. The bot must ignore the command.
- [ ] As a **non-admin**, try tapping any inline button under a host in `/list`. The bot must show an Alert: "⛔ Тільки адміністратори можуть керувати налаштуваннями."
- [ ] As an admin, quickly tap the "🔍 Перевірити" inline button multiple times. A Toast/Alert "⏳ Зачекайте Х с..." must appear.

## 7. Reports Scheduler
- [ ] In `/settings`, set the report time to 1 minute ahead of the current local time (respecting the configured timezone).
- [ ] Wait for the minute to pass.
- [ ] Verify the bot sends the "Щоденний звіт про відключення" (Daily outage report).
- [ ] (Optional) If today is Sunday or the last day of the month, verify weekly/monthly reports are sent accordingly.
- [ ] Enable "🙈 Порожні щоденні: Пропускати". Change the report time to the next minute. If the host had no outages in 24 hours, the report **must not** be sent.
- [ ] Disable reports entirely ("📊 Звіти: Вимкнено"), change time to the next minute. The report **must not** be sent.
