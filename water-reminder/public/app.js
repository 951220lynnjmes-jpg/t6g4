(() => {
  'use strict';

  const SETTINGS_KEY = 'waterReminder.settings.v1';
  const LOG_KEY = 'waterReminder.log.v1';
  const RING_CIRCUMFERENCE = 2 * Math.PI * 68;
  const CLIMATE_LABELS = {
    '1': '一般',
    '1.15': '炎熱',
    '1.08': '乾燥',
    '1.05': '寒冷'
  };

  const el = {
    today: document.getElementById('todayLabel'),
    calcForm: document.getElementById('calcForm'),
    weight: document.getElementById('weightInput'),
    exercise: document.getElementById('exerciseInput'),
    climate: document.getElementById('climateInput'),
    calcHint: document.getElementById('calcHint'),
    ringFill: document.getElementById('ringFill'),
    ringPercent: document.getElementById('ringPercent'),
    goalLiters: document.getElementById('goalLiters'),
    remainingMl: document.getElementById('remainingMl'),
    goalBadge: document.getElementById('goalBadge'),
    goalFoot: document.getElementById('goalFoot'),
    consumedMl: document.getElementById('consumedMl'),
    cupCount: document.getElementById('cupCount'),
    history: document.getElementById('historyList'),
    undo: document.getElementById('undoBtn'),
    reset: document.getElementById('resetBtn'),
    customForm: document.getElementById('customAddForm'),
    customMl: document.getElementById('customMl'),
    reminderCard: document.querySelector('.reminder'),
    reminderPill: document.getElementById('reminderPill'),
    reminderState: document.getElementById('reminderState'),
    nextReminder: document.getElementById('nextReminder'),
    interval: document.getElementById('intervalInput'),
    start: document.getElementById('startInput'),
    end: document.getElementById('endInput'),
    toggle: document.getElementById('reminderToggle'),
    test: document.getElementById('testBtn'),
    toast: document.getElementById('toast')
  };

  let settings = loadSettings();
  let log = loadLog();
  let nextReminderAt = null;
  let toastTimer = null;
  let audioContext = null;

  function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
  }

  function toNumber(value, fallback = 0) {
    const n = Number(String(value).trim());
    return Number.isFinite(n) ? n : fallback;
  }

  function todayKey() {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  }

  function computeGoal(weight, exercise, climate) {
    const total = (weight * 30 + exercise * 12) * climate;
    return clamp(Math.round(total / 10) * 10, 1000, 6000);
  }

  function loadSettings() {
    const base = {
      weight: 60,
      exercise: 30,
      climate: '1',
      goal: 0,
      reminder: {
        enabled: false,
        interval: 60,
        start: '09:00',
        end: '21:00'
      }
    };

    try {
      const saved = JSON.parse(localStorage.getItem(SETTINGS_KEY) || 'null');
      if (saved && typeof saved === 'object') {
        base.weight = toNumber(saved.weight, base.weight);
        base.exercise = toNumber(saved.exercise, base.exercise);
        base.climate = String(saved.climate || base.climate);
        base.goal = toNumber(saved.goal, 0);
        if (saved.reminder && typeof saved.reminder === 'object') {
          base.reminder.enabled = Boolean(saved.reminder.enabled);
          base.reminder.interval = toNumber(saved.reminder.interval, 60);
          base.reminder.start = String(saved.reminder.start || '09:00');
          base.reminder.end = String(saved.reminder.end || '21:00');
        }
      }
    } catch (error) {
      // 忽略損壞的設定，使用預設值。
    }

    base.weight = clamp(base.weight, 20, 250);
    base.exercise = clamp(base.exercise, 0, 600);
    if (!CLIMATE_LABELS[base.climate]) base.climate = '1';
    base.reminder.interval = [15, 30, 45, 60, 90, 120].includes(base.reminder.interval)
      ? base.reminder.interval
      : 60;

    if (!base.goal || base.goal < 500) {
      base.goal = computeGoal(base.weight, base.exercise, Number(base.climate));
    }

    return base;
  }

  function saveSettings() {
    try {
      localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
    } catch (error) {
      // 瀏覽器可能停用儲存空間，忽略即可。
    }
  }

  function loadLog() {
    const key = todayKey();
    try {
      const saved = JSON.parse(localStorage.getItem(LOG_KEY) || 'null');
      if (saved && saved.date === key && Array.isArray(saved.entries)) {
        return {
          date: key,
          entries: saved.entries
            .filter((entry) => entry && Number.isFinite(Number(entry.ml)) && Number(entry.ml) > 0)
            .map((entry) => ({
              ml: Math.round(Number(entry.ml)),
              time: String(entry.time || '')
            }))
        };
      }
    } catch (error) {
      // 忽略損壞的紀錄。
    }
    return { date: key, entries: [] };
  }

  function saveLog() {
    try {
      localStorage.setItem(LOG_KEY, JSON.stringify(log));
    } catch (error) {
      // 忽略儲存失敗。
    }
  }

  function getTotal() {
    return log.entries.reduce((sum, entry) => sum + entry.ml, 0);
  }

  function formatMl(value) {
    return Number(value).toLocaleString('en-US');
  }

  function formatTime(date) {
    return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
  }

  function formatLiters(ml) {
    return `${(ml / 1000).toFixed(2).replace(/\.?0+$/, '')} L`;
  }

  function formatDuration(seconds) {
    const total = Math.max(0, Math.ceil(seconds));
    const h = Math.floor(total / 3600);
    const m = Math.floor((total % 3600) / 60);
    const s = total % 60;
    if (h > 0) return `${h} 小時 ${m} 分`;
    return `${m} 分 ${s} 秒`;
  }

  function updateTodayLabel() {
    try {
      el.today.textContent = new Intl.DateTimeFormat('zh-Hant-TW', {
        month: 'long',
        day: 'numeric',
        weekday: 'long'
      }).format(new Date());
    } catch (error) {
      el.today.textContent = new Date().toLocaleDateString();
    }
  }

  function updateCalcHint() {
    const label = CLIMATE_LABELS[settings.climate] || '一般';
    el.calcHint.textContent =
      `體重 ${settings.weight} kg × 30 ml ＋ 運動 ${settings.exercise} 分鐘 × 12 ml，` +
      `再依「${label}」氣候調整。`;
  }

  function renderGoal() {
    const goal = settings.goal;
    const consumed = getTotal();
    const ratio = goal > 0 ? consumed / goal : 0;
    const percent = Math.min(100, Math.round(ratio * 100));

    el.ringFill.style.strokeDashoffset = String(RING_CIRCUMFERENCE * (1 - Math.min(1, ratio)));
    el.ringPercent.textContent = `${percent}%`;

    el.goalLiters.textContent = formatLiters(goal);
    el.remainingMl.textContent = consumed >= goal
      ? '0 ml'
      : `${formatMl(goal - consumed)} ml`;
    el.goalBadge.textContent = consumed >= goal ? '已達標' : '補水中';

    el.goalFoot.textContent = consumed >= goal
      ? '今天的目標達成了，繼續保持。'
      : `目標約 ${Math.ceil(goal / 250)} 杯水（每杯 250 ml）`;
  }

  function renderTracker() {
    const consumed = getTotal();
    const cups = Math.floor(consumed / 250);
    const lastEntry = log.entries.length ? log.entries[log.entries.length - 1] : null;

    el.consumedMl.textContent = formatMl(consumed);
    el.cupCount.textContent = lastEntry
      ? `約 ${cups} 杯 · 最後一次 ${lastEntry.time}`
      : '約 0 杯 · 尚無紀錄';

    el.history.replaceChildren();
    if (!log.entries.length) {
      const empty = document.createElement('li');
      empty.className = 'empty';
      empty.textContent = '還沒有紀錄，先喝一杯吧。';
      el.history.appendChild(empty);
    } else {
      [...log.entries].reverse().forEach((entry) => {
        const item = document.createElement('li');
        const amount = document.createElement('strong');
        amount.textContent = `+${formatMl(entry.ml)} ml`;
        const time = document.createElement('time');
        time.textContent = entry.time;
        item.append(amount, time);
        el.history.appendChild(item);
      });
    }

    el.undo.disabled = log.entries.length === 0;
  }

  function isValidWindow() {
    return settings.reminder.start < settings.reminder.end;
  }

  function timeToDate(base, hhmm) {
    const [hours, minutes] = hhmm.split(':').map(Number);
    const date = new Date(base);
    date.setHours(hours || 0, minutes || 0, 0, 0);
    return date;
  }

  function computeNextReminder(now, fromNow) {
    const reminder = settings.reminder;
    const start = timeToDate(now, reminder.start);
    const end = timeToDate(now, reminder.end);

    if (start >= end) return null;

    if (now < start) return start;

    if (now >= end) {
      const tomorrow = new Date(now);
      tomorrow.setDate(tomorrow.getDate() + 1);
      return timeToDate(tomorrow, reminder.start);
    }

    if (fromNow) {
      const candidate = new Date(now.getTime() + reminder.interval * 60000);
      if (candidate < end) return candidate;
      const tomorrow = new Date(now);
      tomorrow.setDate(tomorrow.getDate() + 1);
      return timeToDate(tomorrow, reminder.start);
    }

    return new Date(now.getTime() + reminder.interval * 60000);
  }

  function scheduleNext(fromNow) {
    nextReminderAt = computeNextReminder(new Date(), fromNow !== false);
  }

  function describeNextReminder() {
    const reminder = settings.reminder;
    const now = new Date();
    const start = timeToDate(now, reminder.start);
    const end = timeToDate(now, reminder.end);

    if (start >= end) return '提醒時段設定有誤，請確認開始時間早於結束時間。';
    if (now < start) return `提醒將於今天 ${reminder.start} 開始。`;
    if (now >= end) return `今天的提醒時段已結束，明天 ${reminder.start} 再見。`;
    if (!nextReminderAt) return '正在計算下一次提醒時間。';

    if (nextReminderAt.toDateString() !== now.toDateString()) {
      return `今天的提醒時段已結束，明天 ${reminder.start} 再見。`;
    }

    const diff = nextReminderAt.getTime() - now.getTime();
    if (diff <= 0) return '提醒即將送出。';
    return `下次提醒 ${formatTime(nextReminderAt)}，還有 ${formatDuration(diff / 1000)}。`;
  }

  function intervalText(minutes) {
    if (minutes < 60) return `${minutes} 分鐘`;
    if (minutes % 60 === 0) return `${minutes / 60} 小時`;
    return `${Math.floor(minutes / 60)} 小時 ${minutes % 60} 分鐘`;
  }

  function renderReminder() {
    const reminder = settings.reminder;
    const active = reminder.enabled;

    el.reminderCard.classList.toggle('is-active', active);
    el.reminderPill.classList.toggle('is-on', active);
    el.reminderPill.innerHTML = `<i></i>${active ? '已開啟' : '未開啟'}`;
    el.toggle.textContent = active ? '暫停提醒' : '開啟提醒';
    el.reminderState.textContent = active
      ? `${intervalText(reminder.interval)}提醒 · ${reminder.start}–${reminder.end}`
      : '提醒目前關閉';

    if (active) {
      el.nextReminder.textContent = describeNextReminder();
    } else {
      el.nextReminder.textContent = '開啟後，會在提醒時段內定時通知你。';
    }
  }

  function renderAll() {
    updateTodayLabel();
    updateCalcHint();
    renderGoal();
    renderTracker();
    renderReminder();
  }

  function ensureToday() {
    const key = todayKey();
    if (log.date !== key) {
      log = { date: key, entries: [] };
      updateTodayLabel();
      return true;
    }
    return false;
  }

  function showToast(message, duration = 3400) {
    el.toast.textContent = message;
    el.toast.classList.add('show');
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(() => {
      el.toast.classList.remove('show');
    }, duration);
  }

  function addWater(amount) {
    const ml = Math.round(toNumber(amount, 0));
    if (!Number.isFinite(ml) || ml <= 0) {
      showToast('請輸入有效的飲水量。');
      return;
    }

    const reset = ensureToday();
    if (reset) saveLog();

    const before = getTotal();
    const now = new Date();
    log.entries.push({ ml: clamp(ml, 1, 5000), time: formatTime(now) });
    saveLog();

    const after = getTotal();
    renderAll();

    if (before < settings.goal && after >= settings.goal) {
      showToast(`目標達成！今天已喝 ${formatMl(after)} ml。`, 5000);
    } else {
      showToast(`已記錄 ${formatMl(ml)} ml，今天共 ${formatMl(after)} ml。`);
    }
  }

  function undoLast() {
    if (!log.entries.length) return;
    const removed = log.entries.pop();
    saveLog();
    renderAll();
    showToast(`已撤銷 ${formatMl(removed.ml)} ml 的紀錄。`);
  }

  function ensureAudio() {
    const AudioCtor = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtor) return null;
    if (!audioContext) {
      try {
        audioContext = new AudioCtor();
      } catch (error) {
        return null;
      }
    }
    if (audioContext.state === 'suspended') {
      audioContext.resume().catch(() => {});
    }
    return audioContext;
  }

  function playChime() {
    const ctx = ensureAudio();
    if (!ctx) return;
    const now = ctx.currentTime;
    [0, 0.2].forEach((offset, index) => {
      const oscillator = ctx.createOscillator();
      const gain = ctx.createGain();
      oscillator.type = 'sine';
      oscillator.frequency.value = index === 0 ? 660 : 880;
      gain.gain.setValueAtTime(0.0001, now + offset);
      gain.gain.exponentialRampToValueAtTime(0.12, now + offset + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, now + offset + 0.18);
      oscillator.connect(gain);
      gain.connect(ctx.destination);
      oscillator.start(now + offset);
      oscillator.stop(now + offset + 0.2);
    });
  }

  function notify(title, body) {
    if (!('Notification' in window) || Notification.permission !== 'granted') {
      return false;
    }

    const options = {
      body,
      icon: './icon-192.png',
      badge: './icon-192.png',
      tag: 'water-reminder',
      renotify: true,
      data: { url: './' }
    };

    try {
      if ('serviceWorker' in navigator) {
        navigator.serviceWorker.ready
          .then((registration) => registration.showNotification(title, options))
          .catch(() => {
            try {
              new Notification(title, options);
            } catch (error) {
              // 忽略通知失敗。
            }
          });
      } else {
        new Notification(title, options);
      }
      return true;
    } catch (error) {
      return false;
    }
  }

  function fireReminder() {
    const remaining = Math.max(0, settings.goal - getTotal());
    const body = remaining > 0
      ? `今天還需要 ${formatMl(remaining)} ml，先喝杯水吧。`
      : '今天的目標達成了，再補充一點水分也不錯。';

    notify('該喝水了', body);
    showToast(body, 7000);
    playChime();
  }

  async function requestNotificationPermission() {
    if (!('Notification' in window)) return 'unsupported';
    if (Notification.permission === 'granted') return 'granted';
    if (Notification.permission === 'denied') return 'denied';
    try {
      return await Notification.requestPermission();
    } catch (error) {
      return 'denied';
    }
  }

  async function enableReminder() {
    if (!isValidWindow()) {
      showToast('請確認開始時間早於結束時間。');
      return;
    }

    const permission = await requestNotificationPermission();
    settings.reminder.enabled = true;
    saveSettings();
    scheduleNext(true);
    renderReminder();

    if (permission === 'granted') {
      showToast(
        `提醒已開啟，${intervalText(settings.reminder.interval)}提醒一次。`,
        4200
      );
    } else if (permission === 'denied') {
      showToast('通知權限未開啟，仍會在頁面內顯示喝水提示。', 4600);
    } else if (permission === 'unsupported') {
      showToast('此瀏覽器不支援通知，仍會在頁面內顯示喝水提示。', 4600);
    } else {
      showToast('提醒已開啟。', 3000);
    }
  }

  function disableReminder() {
    settings.reminder.enabled = false;
    nextReminderAt = null;
    saveSettings();
    renderReminder();
    showToast('提醒已暫停。');
  }

  async function sendTestNotification() {
    const permission = await requestNotificationPermission();
    if (permission === 'granted') {
      const sent = notify('喝水提醒（測試）', '通知設定成功，時間到了我會提醒你。');
      showToast(sent ? '已送出測試通知。' : '通知傳送失敗，請確認瀏覽器設定。');
    } else if (permission === 'denied') {
      showToast('通知權限已被封鎖，這是頁面內的測試提示。', 4600);
    } else {
      showToast('此瀏覽器不支援通知，這是頁面內的測試提示。', 4600);
    }
    playChime();
  }

  function tick() {
    if (ensureToday()) {
      saveLog();
      renderAll();
      showToast('新的一天開始了，紀錄已重置。');
    }

    if (!settings.reminder.enabled) return;

    const now = new Date();
    if (!nextReminderAt) {
      scheduleNext(true);
      renderReminder();
      return;
    }

    if (now.getTime() >= nextReminderAt.getTime()) {
      const start = timeToDate(now, settings.reminder.start);
      const end = timeToDate(now, settings.reminder.end);
      if (now >= start && now < end) {
        fireReminder();
      }
      nextReminderAt = computeNextReminder(now, true);
      renderReminder();
    } else {
      el.nextReminder.textContent = describeNextReminder();
    }
  }

  function bindEvents() {
    el.calcForm.addEventListener('submit', (event) => {
      event.preventDefault();

      const weight = clamp(toNumber(el.weight.value, settings.weight), 20, 250);
      const exercise = clamp(toNumber(el.exercise.value, settings.exercise), 0, 600);
      const climate = CLIMATE_LABELS[el.climate.value] ? el.climate.value : '1';

      settings.weight = Math.round(weight * 10) / 10;
      settings.exercise = Math.round(exercise);
      settings.climate = climate;
      settings.goal = computeGoal(settings.weight, settings.exercise, Number(climate));
      saveSettings();

      el.weight.value = settings.weight;
      el.exercise.value = settings.exercise;
      el.climate.value = climate;

      renderAll();
      showToast(`每日目標更新為 ${formatMl(settings.goal)} ml。`, 4200);
    });

    document.querySelectorAll('.quick').forEach((button) => {
      button.addEventListener('click', () => addWater(button.dataset.ml));
    });

    el.customForm.addEventListener('submit', (event) => {
      event.preventDefault();
      const amount = toNumber(el.customMl.value, 0);
      if (amount <= 0) {
        showToast('請輸入大於 0 的飲水量。');
        return;
      }
      addWater(amount);
      el.customMl.value = '';
    });

    el.undo.addEventListener('click', undoLast);

    el.reset.addEventListener('click', () => {
      if (!log.entries.length) return;
      if (!window.confirm('確定要清除今天的飲水紀錄嗎？')) return;
      log = { date: todayKey(), entries: [] };
      saveLog();
      renderAll();
      showToast('今天的飲水紀錄已清除。');
    });

    el.interval.addEventListener('change', () => {
      settings.reminder.interval = toNumber(el.interval.value, 60);
      saveSettings();
      if (settings.reminder.enabled) scheduleNext(true);
      renderReminder();
    });

    el.start.addEventListener('change', () => {
      const previous = settings.reminder.start;
      settings.reminder.start = el.start.value || previous;
      if (!isValidWindow()) {
        settings.reminder.start = previous;
        el.start.value = previous;
        showToast('開始時間需早於結束時間，時段未變更。');
        return;
      }
      saveSettings();
      if (settings.reminder.enabled) scheduleNext(true);
      renderReminder();
    });

    el.end.addEventListener('change', () => {
      const previous = settings.reminder.end;
      settings.reminder.end = el.end.value || previous;
      if (!isValidWindow()) {
        settings.reminder.end = previous;
        el.end.value = previous;
        showToast('結束時間需晚於開始時間，時段未變更。');
        return;
      }
      saveSettings();
      if (settings.reminder.enabled) scheduleNext(true);
      renderReminder();
    });

    el.toggle.addEventListener('click', () => {
      if (settings.reminder.enabled) {
        disableReminder();
      } else {
        enableReminder();
      }
    });

    el.test.addEventListener('click', sendTestNotification);

    document.addEventListener('pointerdown', ensureAudio, { once: true });
    document.addEventListener('keydown', ensureAudio, { once: true });
    document.addEventListener('visibilitychange', () => {
      if (!document.hidden) tick();
    });
  }

  function registerServiceWorker() {
    if (!('serviceWorker' in navigator)) return;
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('./sw.js').catch(() => {
        // 離線功能註冊失敗時不影響主要功能。
      });
    });
  }

  function init() {
    el.weight.value = settings.weight;
    el.exercise.value = settings.exercise;
    el.climate.value = settings.climate;
    el.interval.value = String(settings.reminder.interval);
    el.start.value = settings.reminder.start;
    el.end.value = settings.reminder.end;

    renderAll();
    bindEvents();
    registerServiceWorker();

    if (settings.reminder.enabled) {
      scheduleNext(true);
      renderReminder();
    }

    window.setInterval(tick, 1000);
  }

  init();
})();
