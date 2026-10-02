/* Official X widgets only. Reloads and embedded posts are NOT X view counts.
   https://docs.x.com/x-for-websites/embedded-posts/overview
   https://help.x.com/en/using-x/view-counts */
(() => {
  'use strict';
  const SCRIPT = 'https://platform.twitter.com/widgets.js';
  const records = new Map();
  const queue = [];
  let sdkPromise = null, active = 0, scanPending = false;
  const MAX_ACTIVE = 3;

  function loadSDK() {
    if (window.twttr?.widgets?.createTweet) return Promise.resolve(window.twttr);
    if (sdkPromise) return sdkPromise;
    sdkPromise = new Promise((resolve, reject) => {
      let settled = false;
      const script = document.createElement('script');
      const timer = setTimeout(() => finish(new Error('sdk-timeout')), 15000);
      function finish(error) {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        if (error) { script.remove(); reject(error); }
        else resolve(window.twttr);
      }
      if (!window.twttr) window.twttr = { _e: [], ready(fn) { this._e.push(fn); } };
      window.twttr.ready(() => {
        if (window.twttr?.widgets?.createTweet) finish();
      });
      script.id = 'nabd-x-widgets';
      script.async = true;
      script.src = SCRIPT;
      script.referrerPolicy = 'no-referrer';
      script.onload = () => { if (window.twttr?.widgets?.createTweet) finish(); };
      script.onerror = () => finish(new Error('sdk-unavailable'));
      document.head.appendChild(script);
    });
    return sdkPromise;
  }
  function optionsKey() { return state.settings.theme + ':' + state.settings.showMedia; }
  function updateSummary() {
    const label = document.getElementById('x-embed-summary');
    if (!label) return;
    const entries = [...records.values()].filter(r => r.card.isConnected);
    const ready = entries.filter(r => r.status === 'ready').length;
    const failed = entries.filter(r => r.status === 'error').length;
    label.textContent = `${ready} إطارات تضمين جاهزة${failed ? ' · '+failed+' تعذّر تحميلها' : ''}`;
    label.title = 'حالة تحميل الإطارات فقط، وليست عدد مشاهدات X.';
  }
  function fit(record) {
    if (!record.card.isConnected) return;
    const width = record.stage.clientWidth;
    if (!width) return;
    const requested = (state.settings.scale / 100) * (state.cards[record.id]?.scale || 1);
    const scale = Math.min(requested, width / 250);
    record.host.style.zoom = String(scale);
    record.host.style.width = Math.max(250, Math.min(550, width / scale)) + 'px';
  }
  function status(record, value) {
    record.status = value;
    record.card.dataset.embedStatus = value;
    record.card.querySelector('.x-embed-message').textContent = ({
      waiting: 'تضمين X الرسمي جاهز للتحميل عند ظهوره على الشاشة.',
      queued: 'جارٍ تجهيز التضمين الرسمي...',
      loading: 'جارٍ تحميل التغريدة من X...',
      ready: 'تضمين X الرسمي',
      error: 'تعذّر تحميل تضمين X. قد يكون المنشور مقيّدًا أو محذوفًا، أو الاتصال محجوبًا.'
    })[value];
    record.card.querySelector('.x-retry').hidden = value !== 'error';
    record.stage.setAttribute('aria-busy', String(value === 'loading' || value === 'queued'));
    updateSummary();
  }
  async function mount(record) {
    if (!record.card.isConnected) return;
    status(record, 'loading');
    const token = ++record.generation;
    let timeout;
    try {
      const sdk = await loadSDK();
      if (!record.card.isConnected || token !== record.generation) return;
      fit(record);
      const target = record.host;
      const result = await Promise.race([
        sdk.widgets.createTweet(record.id, target, {
          theme: state.settings.theme, lang: 'ar', align: 'center',
          conversation: 'none', cards: state.settings.showMedia ? 'visible' : 'hidden',
          dnt: true
        }),
        new Promise((_, reject) => { timeout = setTimeout(() => reject(new Error('embed-timeout')), 20000); })
      ]);
      if (token !== record.generation || !record.card.isConnected) return;
      if (!result || !target.querySelector('iframe')) throw new Error('embed-unavailable');
      status(record, 'ready');
      fit(record);
    } catch (_) {
      if (token !== record.generation || !record.card.isConnected) return;
      // Detach the old target so a late SDK response cannot replace the fallback.
      const replacement = document.createElement('div');
      replacement.className = 'x-widget-host';
      record.host.replaceWith(replacement);
      record.host = replacement;
      status(record, 'error');
      fit(record);
    } finally { clearTimeout(timeout); }
  }
  function pump() {
    while (active < MAX_ACTIVE && queue.length) {
      const record = queue.shift();
      if (!record.card.isConnected || record.status !== 'queued') continue;
      active++;
      mount(record).finally(() => { active--; pump(); });
    }
  }
  function enqueue(record) {
    if (!record.card.isConnected || record.status !== 'waiting' || document.hidden) return;
    if (platform === 'facebook' && view !== 'saved') return;
    status(record, 'queued'); queue.push(record); pump();
  }
  const intersection = typeof IntersectionObserver === 'function' ? new IntersectionObserver(entries => {
    for (const entry of entries) if (entry.isIntersecting) {
      const record = records.get(entry.target.dataset.id);
      if (record) enqueue(record);
    }
  }, { rootMargin: '250px 0px' }) : null;
  const resize = typeof ResizeObserver === 'function' ? new ResizeObserver(entries => {
    for (const entry of entries) {
      const record = records.get(entry.target.closest('.tweet')?.dataset.id);
      if (record) fit(record);
    }
  }) : null;

  function update(card, post) {
    const c = state.cards[post.id] || {};
    card.classList.toggle('pinned', !!c.pinned);
    card.classList.toggle('wide', !!c.wide);
    card.classList.toggle('new', newIds.has(post.id));
    card.draggable = !isScreen && state.settings.sort === 'custom';
    card.style.setProperty('--card-scale', c.scale || 1);
    card.querySelector('.pin-note').hidden = !c.pinned;
    card.querySelector('.sizeval').textContent = Math.round((c.scale || 1) * 100) + '%';
    card.querySelector('[data-action="pin"]').classList.toggle('on', !!c.pinned);
    card.querySelector('[data-action="bookmark"]').classList.toggle('on', !!c.saved);
    card.querySelector('[data-action="wide"]').classList.toggle('on', !!c.wide);
    card.querySelector('.x-source-label').textContent = post.manual ? 'رابط مضاف يدويًا' : 'من @' + (post.sources[0] || post.handle);
    const record = records.get(post.id);
    if (record) fit(record);
  }
  cardHTML = function(post) {
    const tool = (action, label, symbol, extra = '') => `<button class="iconbtn ${extra}" data-action="${action}" data-id="${post.id}" title="${label}" aria-label="${label}">${icon(symbol)}</button>`;
    return `<article class="tweet x-embedded-card" data-id="${post.id}" data-embed-status="waiting">
      <div class="pin-note" hidden>${icon('pin')} مثبّتة في الأعلى</div>
      <header class="x-embed-header"><span class="pill">تضمين X الرسمي</span><span class="x-source-label tiny muted"></span></header>
      <div class="x-embed-stage" aria-busy="false"><div class="x-widget-host"></div></div>
      <div class="x-embed-fallback"><p class="x-embed-message" role="status">جارٍ تجهيز التضمين الرسمي...</p><button class="btn sm x-retry" data-action="retry-x-embed" data-id="${post.id}" hidden>إعادة محاولة التضمين</button></div>
      <a class="x-original" href="${esc(postUrl(post))}" target="_blank" rel="noopener noreferrer nofollow">فتح التغريدة الأصلية على X ${icon('external')}</a>
      <div class="tweet-tools">${tool('pin','تثبيت التغريدة','pin')}${tool('bookmark','حفظ التغريدة','bookmark')}${tool('copy-post','نسخ رابط التغريدة','link')}<span class="spacer"></span>${tool('post-smaller','تصغير التغريدة','minus')}<span class="sizeval">100%</span>${tool('post-larger','تكبير التغريدة','plus')}${tool('wide','توسيع بطاقة التغريدة','expand')}${tool('move-up','نقل التغريدة إلى الأعلى','up')}${tool('move-down','نقل التغريدة إلى الأسفل','down')}${tool('hide','إخفاء التغريدة','trash','danger')}</div>
    </article>`;
  };
  function scan() {
    scanPending = false;
    for (const [id, record] of records) if (!record.card.isConnected) {
      record.generation++; intersection?.unobserve(record.card); resize?.unobserve(record.stage); records.delete(id);
    }
    const posts = new Map(selectedPosts().map(p => [p.id, p]));
    for (const card of document.querySelectorAll('#feed > .x-embedded-card')) {
      const id = card.dataset.id;
      let record = records.get(id);
      if (!record || record.card !== card) {
        record = { id, card, stage: card.querySelector('.x-embed-stage'), host: card.querySelector('.x-widget-host'), status: 'waiting', generation: 0, key: optionsKey() };
        records.set(id, record); intersection?.observe(card); resize?.observe(record.stage);
        status(record, 'waiting');
      }
      const post = posts.get(id);
      if (post) update(card, post);
      if (record.key !== optionsKey()) {
        record.generation++; record.key = optionsKey();
        const replacement = document.createElement('div'); replacement.className = 'x-widget-host';
        record.host.replaceWith(replacement); record.host = replacement; status(record, 'waiting');
      }
      fit(record);
      const rect = card.getBoundingClientRect();
      if (rect.width && rect.height && rect.bottom > -250 && rect.top < innerHeight + 250) enqueue(record);
    }
    updateSummary();
  }
  function scheduleScan() { if (!scanPending) { scanPending = true; requestAnimationFrame(scan); } }
  const renderFeedBeforeEmbed = renderFeed;
  renderFeed = function() { renderFeedBeforeEmbed(); scan(); };
  const slideBeforeEmbed = renderSlide;
  renderSlide = function() { slideBeforeEmbed(); scheduleScan(); };
  actions['retry-x-embed'] = el => {
    const record = records.get(el.dataset.id);
    if (!record || record.status !== 'error') return;
    if (!window.twttr?.widgets?.createTweet) sdkPromise = null;
    status(record, 'waiting'); enqueue(record);
  };
  document.addEventListener('visibilitychange', scheduleScan);
  window.addEventListener('resize', scheduleScan, { passive: true });
  document.getElementById('feed').insertAdjacentHTML('beforebegin', `<aside class="x-embed-note"><div><b>عرض مضمّن من X</b><span id="x-embed-summary"></span></div><p>التضمين والتحديث التلقائي لا يزيدان عداد مشاهدات X، بحسب مركز مساعدة المنصة. زر فتح الأصل يفتح التغريدة عند ضغطك فقط. <a href="https://help.x.com/en/using-x/view-counts" target="_blank" rel="noopener noreferrer nofollow">تفاصيل احتساب المشاهدات</a></p></aside>`);
  const appearanceBeforeEmbed = actions.appearance;
  actions.appearance = (...args) => {
    const result = appearanceBeforeEmbed(...args);
    if (modalType === 'appearance') {
      const toggle = document.querySelector('[data-setting="showStats"]');
      if (toggle) { toggle.disabled = true; toggle.closest('label').title = 'أرقام وأزرار التفاعل داخل التضمين يتحكم بها X.'; }
      document.getElementById('modal-body').insertAdjacentHTML('afterbegin', '<p class="v2-note">تُعرض التغريدة نفسها بتضمين X الرسمي. التكبير يغيّر حجم الإطار كاملًا ضمن عرض البطاقة؛ يمكن توسيع البطاقة لمزيد من المساحة. أرقام وأزرار التفاعل الداخلية يحددها X.</p>');
    }
    return result;
  };
  const footer = document.querySelector('.footer-source');
  if (footer) footer.innerHTML = 'الجلب: FxEmbed · العرض: تضمين X الرسمي';
  window.NabdXEmbeds = Object.freeze({ version: '2.1.0', update, stats: () => ({ renderer: 'official-x-widgets', loaded: [...records.values()].filter(r => r.status === 'ready').length, failed: [...records.values()].filter(r => r.status === 'error').length, total: records.size, active, embeddedViewsCountOnX: false }) });
})();
