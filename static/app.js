(() => {
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

  const toast = (message) => {
    const element = $('#toast');
    element.textContent = message;
    element.classList.add('is-visible');
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => element.classList.remove('is-visible'), 3200);
  };

  // 外观：跟随系统、浅色或深色；选择保存在本机。
  const systemDark = matchMedia('(prefers-color-scheme: dark)');
  let themeChoice = 'system';
  try { themeChoice = localStorage.getItem('theme') || 'system'; } catch {}
  const applyTheme = () => {
    const dark = themeChoice === 'system' ? systemDark.matches : themeChoice === 'dark';
    document.documentElement.dataset.theme = dark ? 'dark' : 'light';
    $('meta[name="theme-color"]').content = dark ? '#161b18' : '#ffffff';
    $$('[data-theme-choice]').forEach((item) => item.setAttribute('aria-checked', item.dataset.themeChoice === themeChoice));
  };
  const chooseTheme = (item) => {
    themeChoice = item.dataset.themeChoice;
    try {
      if (themeChoice === 'system') localStorage.removeItem('theme');
      else localStorage.setItem('theme', themeChoice);
    } catch {}
    applyTheme();
    item.closest('details').open = false;
  };
  systemDark.addEventListener('change', applyTheme);
  applyTheme();

  // 下拉菜单：同一时间只展开一个，点击外部或按 Esc 收起。
  const closeMenus = (except) => $$('details.menu[open]').forEach((menu) => { if (menu !== except) menu.open = false; });

  const share = async (button) => {
    const url = new URL(button.dataset.share, location.origin).href;
    if (navigator.share && matchMedia('(hover: none)').matches) {
      try { await navigator.share({ title: button.dataset.shareTitle, url }); } catch {}
      return;
    }
    try {
      await navigator.clipboard.writeText(url);
      toast('链接已复制，可以分享给同窗了。');
    } catch {
      toast('无法访问剪贴板，请复制地址栏中的链接。');
    }
  };

  // 楼中楼：回复框移到被回复的评论下方，取消后放回原处。
  const startReply = (button) => {
    const form = $('#reply-form');
    const label = $('[data-reply-label]', form);
    label.dataset.default ||= label.textContent;
    label.textContent = '回复 ' + button.dataset.replyName;
    form.elements.parent.value = button.dataset.reply;
    $('[data-cancel-reply]', form).hidden = false;
    $(':scope > .comment-actions', button.closest('.comment')).after(form);
    form.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    form.elements.body.focus({ preventScroll: true });
  };
  const cancelReply = (button) => {
    const form = button.closest('form');
    const label = $('[data-reply-label]', form);
    label.textContent = label.dataset.default;
    form.elements.parent.value = '';
    button.hidden = true;
    $('.reply-slot').append(form);
  };

  // 编辑器：插入文字时优先使用 insertText，保留浏览器的撤销记录。
  const insert = (area, text, start, end) => {
    area.focus();
    area.setSelectionRange(start, end);
    if (!document.execCommand('insertText', false, text)) area.setRangeText(text, start, end, 'end');
  };
  const format = (button) => {
    const area = $('[data-editor]');
    const { selectionStart: start, selectionEnd: end, value } = area;
    const selected = value.slice(start, end);
    if ('line' in button.dataset) {
      const lineStart = value.lastIndexOf('\n', start - 1) + 1;
      const lines = value.slice(lineStart, end).split('\n').map((line) => button.dataset.line + line);
      insert(area, lines.join('\n'), lineStart, end);
    } else if ('link' in button.dataset) {
      const text = selected || '链接文字';
      insert(area, `[${text}](https://)`, start, end);
      area.setSelectionRange(start + text.length + 3, start + text.length + 11);
    } else {
      const mark = button.dataset.wrap;
      const text = selected || '文字';
      insert(area, mark + text + mark, start, end);
      area.setSelectionRange(start + mark.length, start + mark.length + text.length);
    }
  };
  const switchTab = (tab) => {
    const preview = tab.dataset.editorTab === 'preview';
    $('#editor-write').hidden = preview;
    $('#editor-preview').hidden = !preview;
    $$('[data-editor-tab]').forEach((item) => item.setAttribute('aria-selected', item === tab));
  };
  const countWords = () => {
    const area = $('[data-editor]');
    if (area) $('#editor-count').textContent = [...area.value].length + ' 字';
  };

  const clicks = {
    '[data-dismiss]': (target) => target.closest('.notice').remove(),
    '[data-theme-choice]': chooseTheme,
    '[data-share]': share,
    '[data-reply]': startReply,
    '[data-cancel-reply]': cancelReply,
    '[data-editor-tab]': switchTab,
    '[data-wrap], [data-line], [data-link]': format,
  };
  document.addEventListener('click', (event) => {
    for (const [selector, handle] of Object.entries(clicks)) {
      const target = event.target.closest(selector);
      if (target) handle(target);
    }
    closeMenus(event.target.closest('details.menu'));
  });

  document.addEventListener('keydown', (event) => {
    const command = event.metaKey || event.ctrlKey;
    const key = event.key.toLowerCase();
    if (event.key === 'Escape') {
      const menu = $('details.menu[open]');
      if (menu) {
        menu.open = false;
        $('summary', menu).focus();
      }
    } else if (command && key === 'k') {
      event.preventDefault();
      $('.search input').focus();
    } else if (command && key === 'enter' && event.target.matches('textarea')) {
      event.preventDefault();
      event.target.form.requestSubmit();
    } else if (command && (key === 'b' || key === 'i') && event.target.matches('[data-editor]')) {
      event.preventDefault();
      format($(`[data-wrap="${key === 'b' ? '**' : '_'}"]`));
    }
  });

  document.addEventListener('submit', (event) => {
    const form = event.target;
    if (form.dataset.confirm && !confirm(form.dataset.confirm)) {
      event.preventDefault();
      return;
    }
    if (form.dataset.submitLabel) {
      const button = event.submitter || $('[type="submit"]', form);
      button.disabled = true;
      button.textContent = form.dataset.submitLabel;
    }
  });

  // 发帖页有未保存的修改时，离开前提醒。
  const guarded = $('[data-unsaved-guard]');
  if (guarded) {
    let dirty = false;
    guarded.addEventListener('input', () => { dirty = true; });
    guarded.addEventListener('submit', () => { dirty = false; });
    addEventListener('beforeunload', (event) => {
      if (dirty) {
        event.preventDefault();
        event.returnValue = '';
      }
    });
  }

  const updateSections = () => {
    const ranges = $('[data-post-ranges]');
    if (ranges) ranges.hidden = $('[name="access_mode"]:checked')?.value !== 'range';
    const home = $('[data-home-range]');
    if (home) home.hidden = !$('[name="filter_home"]').checked;
  };
  document.addEventListener('input', (event) => {
    if (event.target.matches('[data-editor]')) countWords();
  });
  document.addEventListener('change', (event) => {
    if (event.target.type === 'file') {
      const label = $('[data-file-label]', event.target.closest('.upload'));
      label.textContent = event.target.files[0]?.name || '选择或拖入学信网报告';
    }
    updateSections();
  });
  for (const [type, active] of [['dragenter', true], ['dragleave', false], ['drop', false]]) {
    document.addEventListener(type, (event) => event.target.closest?.('[data-dropzone]')?.classList.toggle('is-dragover', active));
  }

  // 等级区间：两个滑块对应同一段区间，回复区间始终限制在阅读区间内。
  const tiersElement = $('#school-tiers');
  if (tiersElement) {
    const tiers = JSON.parse(tiersElement.textContent);
    const ownRanks = JSON.parse($('#own-ranks')?.textContent || '[]');
    const ranges = $$('[data-tier-range]');
    const input = (box, end) => $('[data-range-' + end + ']', box);
    const number = (box, end) => Number(input(box, end).value);
    const clamp = (value, low, high) => Math.max(low, Math.min(high, value));
    const percent = (index) => index / Math.max(1, tiers.length - 1) * 100 + '%';
    const render = (box) => {
      const low = number(box, 'low');
      const high = number(box, 'high');
      document.getElementById(box.dataset.minField).value = tiers[low].rank;
      document.getElementById(box.dataset.maxField).value = tiers[high].rank;
      $('[data-range-output]', box).textContent = low === high ? tiers[low].name : tiers[low].name + ' — ' + tiers[high].name;
      const selection = $('[data-range-selection]', box);
      selection.style.left = percent(low);
      selection.style.width = (high - low) / Math.max(1, tiers.length - 1) * 100 + '%';
      input(box, 'low').setAttribute('aria-valuetext', tiers[low].name);
      input(box, 'high').setAttribute('aria-valuetext', tiers[high].name);
      input(box, 'low').style.zIndex = low === high && low > 0 ? '4' : '2';
      const home = box.dataset.scope === 'home';
      const valid = home || ownRanks.some((rank) => tiers[low].rank <= rank && rank <= tiers[high].rank);
      const hint = $('[data-range-hint]', box);
      hint.textContent = home ? '只推荐阅读范围完整覆盖这段等级区间的帖子。' : valid ? '加深的等级属于你的学校；区间包含任意一个即可。' : '请让区间包含至少一所本校的等级。';
      hint.classList.toggle('range-warning', !valid);
    };
    const sync = () => {
      const read = ranges.find((box) => box.dataset.scope === 'read');
      const reply = ranges.find((box) => box.dataset.scope === 'reply');
      if (read && reply) {
        for (const end of ['low', 'high']) input(reply, end).value = clamp(number(reply, end), number(read, 'low'), number(read, 'high'));
      }
      ranges.forEach(render);
    };
    if (tiers.length) {
      ranges.forEach((box) => {
        for (const [end, field] of [['low', box.dataset.minField], ['high', box.dataset.maxField]]) {
          const index = tiers.findIndex((tier) => String(tier.rank) === document.getElementById(field).value);
          input(box, end).value = index >= 0 ? index : end === 'low' ? 0 : tiers.length - 1;
          input(box, end).addEventListener('input', () => {
            if (number(box, 'low') > number(box, 'high')) input(box, end === 'low' ? 'high' : 'low').value = number(box, end);
            sync();
          });
        }
        $$('[data-tier-rank]', box).forEach((tick, index) => {
          tick.classList.toggle('is-own', ownRanks.includes(Number(tick.dataset.tierRank)));
          tick.style.left = percent(index);
          tick.style.width = 100 / tiers.length + '%';
        });
      });
      sync();
    }
    const rangeOption = $('[name="access_mode"][value="range"]');
    if (rangeOption) rangeOption.disabled = !ownRanks.length || !tiers.length;
  }

  if (/Mac|iPhone|iPad/.test(navigator.platform)) $$('[data-mod]').forEach((element) => { element.textContent = '⌘'; });
  updateSections();
  countWords();

  document.addEventListener('toast', (event) => toast(event.detail.message));
  document.addEventListener('htmx:responseError', () => toast('操作没有完成，请刷新后重试。'));
  document.addEventListener('htmx:sendError', () => toast('网络连接中断，请稍后重试。'));
  document.addEventListener('htmx:afterSettle', () => {
    const fresh = $('.comment.is-new');
    if (!fresh) return;
    fresh.scrollIntoView({ block: 'center', behavior: 'smooth' });
    setTimeout(() => fresh.classList.remove('is-new'), 2500);
  });
})();
