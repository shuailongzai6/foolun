(() => {
  const toast = (message) => {
    const element = document.querySelector('#toast');
    element.textContent = message;
    element.classList.add('visible');
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => element.classList.remove('visible'), 3200);
  };

  document.addEventListener('click', async (event) => {
    const dismiss = event.target.closest('[data-dismiss]');
    if (dismiss) dismiss.closest('.message').remove();
    const share = event.target.closest('[data-share]');
    if (share) {
      try {
        await navigator.clipboard.writeText(new URL(share.dataset.share, location.origin).href);
        toast('讨论链接已复制，可以分享给同窗了。');
      } catch {
        toast('无法访问剪贴板，请复制浏览器中的讨论网址。');
      }
    }
    const reply = event.target.closest('[data-reply]');
    if (reply) {
      const form = document.querySelector('#reply-form');
      form.elements.parent.value = reply.dataset.reply;
      const label = document.querySelector('#reply-to');
      label.textContent = '回复 ' + reply.dataset.replyName;
      label.hidden = false;
      form.querySelector('[data-cancel-reply]').hidden = false;
      form.scrollIntoView({behavior: 'smooth', block: 'center'});
      form.elements.body.focus({preventScroll: true});
    }
    const cancel = event.target.closest('[data-cancel-reply]');
    if (cancel) {
      const form = cancel.closest('form');
      form.elements.parent.value = '';
      document.querySelector('#reply-to').hidden = true;
      cancel.hidden = true;
    }
    const tab = event.target.closest('[data-editor-tab]');
    if (tab) {
      const preview = tab.dataset.editorTab === 'preview';
      document.querySelector('#editor-write').hidden = preview;
      document.querySelector('#editor-preview').hidden = !preview;
      document.querySelectorAll('[data-editor-tab]').forEach(item => item.classList.toggle('active', item === tab));
    }
    const format = event.target.closest('[data-format], [data-prefix]');
    if (format) {
      const editor = document.querySelector('[data-editor]');
      const start = editor.selectionStart, end = editor.selectionEnd;
      const selected = editor.value.slice(start, end) || '内容';
      const before = format.dataset.prefix || format.dataset.format;
      const after = format.dataset.prefix ? '' : format.dataset.format;
      editor.setRangeText(before + selected + after, start, end, 'select');
      editor.focus();
      editor.dispatchEvent(new Event('input', {bubbles: true}));
    }
    document.querySelectorAll('details[open]').forEach(menu => {
      if (!menu.contains(event.target) && (menu.classList.contains('user-menu') || menu.classList.contains('sort-menu'))) menu.open = false;
    });
  });

  document.addEventListener('submit', (event) => {
    const form = event.target;
    if (form.dataset.confirm && !confirm(form.dataset.confirm)) {
      event.preventDefault();
      return;
    }
    if (form.dataset.submitLabel) {
      const button = form.querySelector('button:not([type="button"])');
      button.disabled = true;
      button.textContent = form.dataset.submitLabel;
    }
  });

  document.addEventListener('change', (event) => {
    if (event.target.type === 'file') {
      const label = event.target.closest('.upload-zone')?.querySelector('[data-file-label]');
      if (label) label.textContent = event.target.files[0]?.name || '点击选择验证报告';
    }
    updatePermissionSections();
  });

  const updatePermissionSections = () => {
    const mode = document.querySelector('[name="access_mode"]:checked')?.value;
    const postRanges = document.querySelector('[data-post-ranges]');
    if (postRanges) postRanges.hidden = mode !== 'range';
    const homeRange = document.querySelector('[data-home-range]');
    if (homeRange) homeRange.hidden = !document.querySelector('[name="filter_home"]').checked;
  };
  updatePermissionSections();

  const tiersElement = document.querySelector('#school-tiers');
  if (tiersElement) {
    const tiers = JSON.parse(tiersElement.textContent);
    const ownRanks = JSON.parse(document.querySelector('#own-ranks')?.textContent || '[]');
    const ranges = [...document.querySelectorAll('[data-tier-range]')];
    const input = (box, end) => box.querySelector('[data-range-' + end + ']');
    const number = (box, end) => Number(input(box, end).value);
    const clamp = (value, low, high) => Math.max(low, Math.min(high, value));
    const render = (box) => {
      const low = number(box, 'low'), high = number(box, 'high');
      document.getElementById(box.dataset.minField).value = tiers[low].rank;
      document.getElementById(box.dataset.maxField).value = tiers[high].rank;
      box.querySelector('[data-range-output]').textContent = low === high ? tiers[low].name : tiers[low].name + ' — ' + tiers[high].name;
      const selection = box.querySelector('[data-range-selection]');
      selection.style.left = low / Math.max(1, tiers.length - 1) * 100 + '%';
      selection.style.width = (high - low) / Math.max(1, tiers.length - 1) * 100 + '%';
      input(box, 'low').setAttribute('aria-valuetext', tiers[low].name);
      input(box, 'high').setAttribute('aria-valuetext', tiers[high].name);
      input(box, 'low').style.zIndex = low === high && low > 0 ? '4' : '2';
      const valid = box.dataset.scope === 'home' || ownRanks.some(rank => tiers[low].rank <= rank && rank <= tiers[high].rank);
      const hint = box.querySelector('[data-range-hint]');
      hint.textContent = box.dataset.scope === 'home' ? '只推荐阅读范围完整覆盖这段等级区间的帖子。' : valid ? '加深的等级属于你的学校；区间内包含任意一个即可。' : '请让区间包含至少一所本校的等级。';
      hint.classList.toggle('range-warning', !valid);
    };
    const sync = () => {
      const read = ranges.find(box => box.dataset.scope === 'read');
      const reply = ranges.find(box => box.dataset.scope === 'reply');
      if (read && reply) {
        for (const end of ['low', 'high']) input(reply, end).value = clamp(number(reply, end), number(read, 'low'), number(read, 'high'));
      }
      ranges.forEach(render);
    };
    if (tiers.length) {
      ranges.forEach(box => {
        for (const [end, field] of [['low', box.dataset.minField], ['high', box.dataset.maxField]]) {
          const index = tiers.findIndex(tier => String(tier.rank) === document.getElementById(field).value);
          input(box, end).value = index >= 0 ? index : end === 'low' ? 0 : tiers.length - 1;
          input(box, end).addEventListener('input', () => {
            if (number(box, 'low') > number(box, 'high')) input(box, end === 'low' ? 'high' : 'low').value = number(box, end);
            sync();
          });
        }
        box.querySelectorAll('[data-tier-rank]').forEach((tick, index) => {
          tick.classList.toggle('is-own', ownRanks.includes(Number(tick.dataset.tierRank)));
          tick.style.left = index / Math.max(1, tiers.length - 1) * 100 + '%';
          tick.style.width = 100 / tiers.length + '%';
        });
      });
      sync();
    }
    const rangeOption = document.querySelector('[name="access_mode"][value="range"]');
    if (rangeOption) rangeOption.disabled = !ownRanks.length || !tiers.length;
  }

  const editor = document.querySelector('[data-editor]');
  if (editor) {
    const updateCount = () => document.querySelector('#editor-count').textContent = editor.value.length + ' 字';
    editor.addEventListener('input', updateCount);
    updateCount();
  }

  document.addEventListener('keydown', (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      document.querySelector('.header-search input').focus();
    }
  });
  document.body.addEventListener('htmx:responseError', () => toast('操作没有完成，请刷新后重试。'));
  document.body.addEventListener('htmx:sendError', () => toast('网络连接中断，请稍后重试。'));
})();
