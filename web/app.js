(() => {
  'use strict';

  const { t, locale } = window.i18n;

  const AUTH_KEY = 'tg.auth';
  const OLD_PLAYER_KEY = 'tradingGamePlayer';
  const MARKET_POLL_MS = 18000;
  const PORTFOLIO_POLL_MS = 15000;

  const state = {
    auth: null,
    player: null,
    assets: [],
    assetBySymbol: new Map(),
    portfolio: null,
    activeTab: 'home',
    marketFilter: 'all',
    addAssetClass: 'stock',
    addAssetSearchResults: [],
    tradeSide: 'buy',
    chart: null,
    chartSymbol: null,
    chartRange: '1mo',
    timers: [],
    deriv: {
      config: null,
      positions: [],
      funding: [],
      showClosed: false,
      direction: 'long',
      kind: 'perp',
      marginTarget: null
    },
    indexRange: 24,
    equityRange: 24,
    indexChartInstance: null,
    equityChartInstance: null,
    sparklines: {},
    feedNewestId: 0,
    alerts: [],
    alertPanelOpen: false,
    season: null
  };

  const el = {};

  document.addEventListener('DOMContentLoaded', init);

  async function init() {
    cacheElements();
    window.i18n.apply();
    bindEvents();
    await restoreSession();
  }

  function cacheElements() {
    Object.assign(el, {
      toastRegion: document.getElementById('toast-region'),
      startScreen: document.getElementById('start-screen'),
      appShell: document.getElementById('app-shell'),
      authTabs: Array.from(document.querySelectorAll('.auth-tab')),
      authForms: Array.from(document.querySelectorAll('.auth-form')),
      signinForm: document.getElementById('signin-form'),
      registerForm: document.getElementById('register-form'),
      recoverForm: document.getElementById('recover-form'),
      authStatus: document.getElementById('auth-status'),
      playerName: document.getElementById('player-name'),
      summaryCash: document.getElementById('summary-cash'),
      summaryNetWorth: document.getElementById('summary-net-worth'),
      summaryPl: document.getElementById('summary-pl'),
      switchPlayer: document.getElementById('switch-player'),
      tabButtons: Array.from(document.querySelectorAll('.tab-button')),
      tabPanels: Array.from(document.querySelectorAll('.tab-panel')),
      assetFilters: document.getElementById('asset-filters'),
      addAssetOpen: document.getElementById('add-asset-open'),
      addAssetModal: document.getElementById('add-asset-modal'),
      addAssetClasses: document.getElementById('add-asset-classes'),
      addAssetForm: document.getElementById('add-asset-form'),
      addAssetQueryLabel: document.getElementById('add-asset-query-label'),
      addAssetQuery: document.getElementById('add-asset-query'),
      addAssetSearch: document.getElementById('add-asset-search'),
      addAssetHelp: document.getElementById('add-asset-help'),
      addAssetResults: document.getElementById('add-asset-results'),
      addAssetSubmit: document.getElementById('add-asset-submit'),
      addAssetMessage: document.getElementById('add-asset-message'),
      marketStatus: document.getElementById('market-status'),
      marketBody: document.getElementById('market-body'),
      portfolioSummary: document.getElementById('portfolio-summary'),
      portfolioEmpty: document.getElementById('portfolio-empty'),
      holdingsBody: document.getElementById('holdings-body'),
      historyEmpty: document.getElementById('history-empty'),
      historyBody: document.getElementById('history-body'),
      leaderboardEmpty: document.getElementById('leaderboard-empty'),
      leaderboardBody: document.getElementById('leaderboard-body'),
      tradeModal: document.getElementById('trade-modal'),
      tradeForm: document.getElementById('trade-form'),
      tradeTitle: document.getElementById('trade-title'),
      tradeSymbol: document.getElementById('trade-symbol'),
      tradeQuantity: document.getElementById('trade-quantity'),
      tradeEstimate: document.getElementById('trade-estimate'),
      tradePriceNote: document.getElementById('trade-price-note'),
      tradeSubmit: document.getElementById('trade-submit'),
      tradeMessage: document.getElementById('trade-message'),
      sideToggles: Array.from(document.querySelectorAll('[data-side]')),
      chartModal: document.getElementById('chart-modal'),
      chartTitle: document.getElementById('chart-title'),
      chartStatus: document.getElementById('chart-status'),
      rangeButtons: document.getElementById('range-buttons'),
      chartCanvas: document.getElementById('price-chart'),
      derivSummary: document.getElementById('deriv-summary'),
      derivStatus: document.getElementById('deriv-status'),
      derivEmpty: document.getElementById('deriv-empty'),
      derivBody: document.getElementById('deriv-body'),
      derivOpenNew: document.getElementById('deriv-open-new'),
      derivFundingBody: document.getElementById('deriv-funding-body'),
      derivFundingEmpty: document.getElementById('deriv-funding-empty'),
      derivToggleClosed: document.getElementById('deriv-toggle-closed'),
      derivClosedSection: document.getElementById('deriv-closed-section'),
      derivClosedBody: document.getElementById('deriv-closed-body'),
      derivClosedEmpty: document.getElementById('deriv-closed-empty'),
      derivModal: document.getElementById('deriv-modal'),
      derivForm: document.getElementById('deriv-form'),
      derivTitle: document.getElementById('deriv-title'),
      derivSymbol: document.getElementById('deriv-symbol'),
      derivLeverage: document.getElementById('deriv-leverage'),
      derivLeverageHint: document.getElementById('deriv-leverage-hint'),
      leveragePresets: document.getElementById('leverage-presets'),
      derivSize: document.getElementById('deriv-size'),
      derivNotional: document.getElementById('deriv-notional'),
      derivMarginEst: document.getElementById('deriv-margin-est'),
      derivLiqEst: document.getElementById('deriv-liq-est'),
      derivFundingEst: document.getElementById('deriv-funding-est'),
      derivKindNote: document.getElementById('deriv-kind-note'),
      derivSubmit: document.getElementById('deriv-submit'),
      derivMessage: document.getElementById('deriv-message'),
      derivDirectionButtons: Array.from(document.querySelectorAll('[data-deriv-direction]')),
      derivKindButtons: Array.from(document.querySelectorAll('[data-deriv-kind]')),
      marginModal: document.getElementById('margin-modal'),
      marginForm: document.getElementById('margin-form'),
      marginTitle: document.getElementById('margin-title'),
      marginAmount: document.getElementById('margin-amount'),
      marginSubmit: document.getElementById('margin-submit'),
      marginMessage: document.getElementById('margin-message'),
      seasonName: document.getElementById('season-name'),
      seasonCountdown: document.getElementById('season-countdown'),
      seasonProgressFill: document.getElementById('season-progress-fill'),
      indexTitle: document.getElementById('index-title'),
      indexValue: document.getElementById('index-value'),
      indexChange: document.getElementById('index-change'),
      indexChart: document.getElementById('index-chart'),
      indexRanges: document.getElementById('index-ranges'),
      movers: document.getElementById('movers'),
      activityFeed: document.getElementById('activity-feed'),
      homeStandings: document.getElementById('home-standings'),
      equityChart: document.getElementById('equity-chart'),
      equityRanges: document.getElementById('equity-ranges'),
      dailyReport: document.getElementById('daily-report'),
      alertBell: document.getElementById('alert-bell'),
      alertCount: document.getElementById('alert-count'),
      alertPanel: document.getElementById('alert-panel'),
      alertList: document.getElementById('alert-list')
    });
  }

  function bindEvents() {
    el.authTabs.forEach((button) => button.addEventListener('click', () => setAuthMode(button.dataset.authMode)));    el.signinForm.addEventListener('submit', handleSignIn);
    el.registerForm.addEventListener('submit', handleRegister);
    el.recoverForm.addEventListener('submit', handleRecover);
    el.switchPlayer.addEventListener('click', logoutPlayer);
    el.tabButtons.forEach((button) => button.addEventListener('click', () => setActiveTab(button.dataset.tab)));
    el.assetFilters.addEventListener('click', handleFilterClick);
    el.addAssetOpen.addEventListener('click', openAddAssetModal);
    el.addAssetClasses.addEventListener('click', handleAddAssetClassClick);
    el.addAssetForm.addEventListener('submit', handleAddAssetSubmit);
    el.addAssetSearch.addEventListener('click', handleAddAssetSearch);
    el.addAssetResults.addEventListener('click', handleAddAssetResultClick);
    el.addAssetQuery.addEventListener('input', handleAddAssetQueryInput);
    el.marketBody.addEventListener('click', handleAssetAction);
    el.holdingsBody.addEventListener('click', handleAssetAction);
    el.leaderboardBody.addEventListener('click', () => {});
    el.tradeSymbol.addEventListener('change', updateTradeEstimate);
    el.tradeQuantity.addEventListener('input', updateTradeEstimate);
    el.tradeForm.addEventListener('submit', handleTradeSubmit);
    el.sideToggles.forEach((button) => button.addEventListener('click', () => setTradeSide(button.dataset.side)));
    el.rangeButtons.addEventListener('click', handleRangeClick);
    document.querySelectorAll('[data-close="trade"]').forEach((button) => button.addEventListener('click', closeTradeModal));
    document.querySelectorAll('[data-close="add-asset"]').forEach((button) => button.addEventListener('click', closeAddAssetModal));
    document.querySelectorAll('[data-close="chart"]').forEach((button) => button.addEventListener('click', closeChartModal));
    document.querySelectorAll('[data-close="deriv"]').forEach((button) => button.addEventListener('click', closeDerivModal));
    document.querySelectorAll('[data-close="margin"]').forEach((button) => button.addEventListener('click', closeMarginModal));
    el.derivOpenNew.addEventListener('click', openDerivModal);
    el.derivForm.addEventListener('submit', handleDerivSubmit);
    el.derivSymbol.addEventListener('change', updateDerivEstimate);
    el.derivSize.addEventListener('input', updateDerivEstimate);
    el.derivLeverage.addEventListener('input', updateDerivEstimate);
    el.leveragePresets.addEventListener('click', handleLeveragePreset);
    el.derivDirectionButtons.forEach((button) => button.addEventListener('click', () => setDerivDirection(button.dataset.derivDirection)));
    el.derivKindButtons.forEach((button) => button.addEventListener('click', () => setDerivKind(button.dataset.derivKind)));
    el.derivBody.addEventListener('click', handleDerivAction);
    el.derivToggleClosed.addEventListener('click', toggleClosedPositions);
    el.marginForm.addEventListener('submit', handleMarginSubmit);
    el.indexRanges.addEventListener('click', handleIndexRange);
    el.equityRanges.addEventListener('click', handleEquityRange);
    el.alertBell.addEventListener('click', toggleAlertPanel);
    document.addEventListener('click', (event) => {
      // Close the alert dropdown on an outside click, the way a menu behaves.
      if (!state.alertPanelOpen) return;
      if (el.alertPanel.contains(event.target) || el.alertBell.contains(event.target)) return;
      state.alertPanelOpen = false;
      el.alertPanel.classList.add('hidden');
    });
    [el.tradeModal, el.addAssetModal, el.chartModal, el.derivModal, el.marginModal].forEach((modal) => {
      modal.addEventListener('click', (event) => {
        if (event.target !== modal) return;
        if (modal === el.tradeModal) closeTradeModal();
        if (modal === el.addAssetModal) closeAddAssetModal();
        if (modal === el.chartModal) closeChartModal();
        if (modal === el.derivModal) closeDerivModal();
        if (modal === el.marginModal) closeMarginModal();
      });
    });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') {
        closeTradeModal();
        closeAddAssetModal();
        closeChartModal();
        closeDerivModal();
        closeMarginModal();
      }
    });
    document.querySelectorAll('[data-lang-toggle]').forEach((button) => {
      button.addEventListener('click', () => window.i18n.toggle());
    });
    document.addEventListener('langchange', rerenderForLanguage);
  }

  // Static markup is re-translated by i18n.apply(); everything the script drew
  // itself has to be rebuilt here so the visible language stays consistent.
  function rerenderForLanguage() {
    const tab = state.activeTab || 'home';
    if (state.player) el.playerName.textContent = state.player.username;
    if (state.assets.length) renderMarket();
    else el.marketBody.innerHTML = rowMessage(5, t('market.loading'));
    if (state.portfolio) {
      renderSummary(state.portfolio);
      renderPortfolio(state.portfolio);
    }
    if (tab === 'history') loadTransactions();
    if (tab === 'leaderboard') loadLeaderboard();
    if (tab === 'home') {
      // Feed text is built from event payloads, so it has to be rebuilt; the
      // cached id is cleared or the "nothing new" guard would skip the redraw.
      state.feedNewestId = 0;
      loadDashboard();
      loadIndex(state.indexRange);
      loadMovers();
    }
    if (tab === 'portfolio') {
      loadEquityCurve();
      loadReport();
    }
    if (tab === 'derivatives') {
      // Status text was written in the previous language and cannot be retranslated.
      setStatus(el.derivStatus, '', '');
      renderPositions();
      renderFunding();
      if (state.deriv.config) setDerivKind(state.deriv.kind);
    }
    if (!el.tradeModal.classList.contains('hidden')) {
      setTradeSide(state.tradeSide);
      updateTradeEstimate();
    }
    if (!el.addAssetModal.classList.contains('hidden')) {
      setAddAssetClass(state.addAssetClass);
      renderAddAssetResults(state.addAssetSearchResults);
    }
    if (!el.chartModal.classList.contains('hidden') && state.chartSymbol) {
      el.chartTitle.textContent = t('chart.titleFor', { symbol: state.chartSymbol });
      loadChart();
    }
  }

  async function restoreSession() {
    const saved = loadSavedAuth();
    if (!saved) {
      clearAuth();
      showStart();
      return;
    }

    state.auth = saved;
    try {
      const me = await apiRequest('/api/me');
      saveAuth({ ...saved, id: me.id, username: me.username });
      showApp();
    } catch (error) {
      if (error.status === 401) {
        clearAuth();
      } else {
        state.auth = null;
        state.player = null;
        state.portfolio = null;
      }
      showStart();
      if (error.status && error.status !== 401) showToast(t('auth.checkFailed', { message: error.message }), 'bad');
    }
  }

  function loadSavedAuth() {
    try {
      const raw = localStorage.getItem(AUTH_KEY);
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      if (!parsed || !parsed.token || !parsed.id || !parsed.username) return null;
      return { token: parsed.token, id: parsed.id, username: parsed.username };
    } catch {
      localStorage.removeItem(AUTH_KEY);
      return null;
    }
  }

  function saveAuth(auth) {
    const clean = { token: auth.token, id: auth.id, username: auth.username };
    localStorage.setItem(AUTH_KEY, JSON.stringify(clean));
    localStorage.removeItem(OLD_PLAYER_KEY);
    state.auth = clean;
    state.player = { id: clean.id, username: clean.username };
  }

  function clearAuth() {
    localStorage.removeItem(AUTH_KEY);
    localStorage.removeItem(OLD_PLAYER_KEY);
    state.auth = null;
    state.player = null;
    state.portfolio = null;
  }

  async function handleSignIn(event) {
    event.preventDefault();
    await submitAuthForm(el.signinForm, '/api/login', ['username', 'password'], t('auth.signingIn'));
  }

  async function handleRegister(event) {
    event.preventDefault();
    await submitAuthForm(el.registerForm, '/api/register', ['username', 'password', 'recovery_word'], t('auth.creating'));
  }

  async function handleRecover(event) {
    event.preventDefault();
    await submitAuthForm(el.recoverForm, '/api/recover', ['username', 'recovery_word', 'new_password'], t('auth.resetting'));
  }

  async function submitAuthForm(form, endpoint, fields, pendingMessage) {
    const body = {};
    const formData = new FormData(form);
    for (const field of fields) {
      body[field] = String(formData.get(field) || '').trim();
      if (!body[field]) {
        setStatus(el.authStatus, t('auth.fillAll'), 'bad');
        return;
      }
    }
    const password = body.password || body.new_password;
    if (password.length < 4) {
      setStatus(el.authStatus, t('auth.passwordTooShort'), 'bad');
      return;
    }

    const button = form.querySelector('button[type="submit"]');
    button.disabled = true;
    setStatus(el.authStatus, pendingMessage, '');
    try {
      const auth = await apiRequest(endpoint, {
        method: 'POST',
        body: JSON.stringify(body)
      });
      saveAuth(auth);
      setStatus(el.authStatus, '', '');
      form.reset();
      showApp();
    } catch (error) {
      setStatus(el.authStatus, error.message, 'bad');
      showToast(error.message, 'bad');
    } finally {
      button.disabled = false;
    }
  }

  function showStart() {
    clearTimers();
    el.startScreen.classList.remove('hidden');
    el.appShell.classList.add('hidden');
    setAuthMode('signin');
  }

  function showApp() {
    el.startScreen.classList.add('hidden');
    el.appShell.classList.remove('hidden');
    el.playerName.textContent = state.player.username;
    setActiveTab(state.activeTab || 'home');
    refreshAll();
    clearTimers();
    state.timers.push(window.setInterval(loadAssets, MARKET_POLL_MS));
    state.timers.push(window.setInterval(loadPortfolio, PORTFOLIO_POLL_MS));
    state.timers.push(window.setInterval(() => {
      if (state.activeTab === 'derivatives') {
        // Positions change fast at high leverage; refresh alerts alongside so a
        // liquidation badge appears with the position disappearing.
        loadPositions();
        loadAlerts();
      }
    }, PORTFOLIO_POLL_MS));
    // The board polls faster than the market: a live tape that updates every
    // 18s does not feel live.
    state.timers.push(window.setInterval(() => {
      if (state.activeTab === 'home') {
        loadDashboard();
        loadIndex(state.indexRange);
      }
    }, 8000));
    // Load once immediately, then poll: waiting a full interval means a
    // liquidation that already happened shows up as a silent badge-less bell.
    loadAlerts();
    state.timers.push(window.setInterval(loadAlerts, 15000));
  }

  async function logoutPlayer() {
    try {
      await apiRequest('/api/logout', { method: 'POST' });
    } catch {
      // Local logout should still succeed if the server is unreachable.
    } finally {
      clearAuth();
      state.activeTab = 'home';
      closeTradeModal();
      closeAddAssetModal();
      closeChartModal();
      showStart();
    }
  }

  function handleSessionExpired() {
    clearAuth();
    state.activeTab = 'home';
    closeTradeModal();
    closeAddAssetModal();
    closeChartModal();
    showStart();
    showToast(t('auth.sessionExpired'), 'bad');
  }

  function setAuthMode(mode) {
    const nextMode = ['signin', 'register', 'recover'].includes(mode) ? mode : 'signin';
    el.authTabs.forEach((button) => button.classList.toggle('active', button.dataset.authMode === nextMode));
    el.authForms.forEach((form) => form.classList.toggle('hidden', form.dataset.authForm !== nextMode));
    setStatus(el.authStatus, '', '');
    const firstInput = document.querySelector(`[data-auth-form="${nextMode}"] input`);
    if (firstInput) firstInput.focus();
  }

  function clearTimers() {
    state.timers.forEach((timer) => window.clearInterval(timer));
    state.timers = [];
  }

  async function refreshAll() {
    await Promise.allSettled([loadAssets(), loadPortfolio(), loadLeaderboard()]);
    if (state.activeTab === 'history') loadTransactions();
  }

  async function loadAssets() {
    setStatus(el.marketStatus, state.assets.length ? t('market.updating') : t('market.loading'), '');
    try {
      const data = await apiRequest('/api/assets');
      state.assets = Array.isArray(data.assets) ? data.assets : [];
      state.assetBySymbol = new Map(state.assets.map((asset) => [asset.symbol, asset]));
      populateTradeSymbols();
      renderMarket();
      setStatus(el.marketStatus, t('market.updated', {
        time: formatTime(data.as_of),
        count: state.assets.length
      }), 'good');
      updateTradeEstimate();
    } catch (error) {
      setStatus(el.marketStatus, state.assets.length ? t('market.updateFailed') : t('market.unavailable'), 'bad');
      showToast(t('toast.market', { message: error.message }), 'bad');
    }
  }

  async function loadPortfolio() {
    if (!state.player) return;
    try {
      const data = await apiRequest(`/api/players/${encodeURIComponent(state.player.id)}/portfolio`);
      state.portfolio = data;
      renderSummary(data);
      renderPortfolio(data);
    } catch (error) {
      if (error.status === 401) return;
      if (error.status === 404) {
        showToast(t('auth.playerGone'), 'bad');
        clearAuth();
        showStart();
        return;
      }
      showToast(t('toast.portfolio', { message: error.message }), 'bad');
      renderPortfolioError(error.message);
    }
  }

  async function loadTransactions() {
    if (!state.player) return;
    el.historyBody.innerHTML = rowLoading(6, t('history.loading'));
    el.historyEmpty.classList.add('hidden');
    try {
      const data = await apiRequest(`/api/players/${encodeURIComponent(state.player.id)}/transactions?limit=100`);
      renderTransactions(data.transactions || []);
    } catch (error) {
      if (error.status === 401) return;
      el.historyBody.innerHTML = rowMessage(6, t('history.unavailable', { message: escapeHtml(error.message) }));
      showToast(t('toast.history', { message: error.message }), 'bad');
    }
  }

  async function loadLeaderboard() {
    el.leaderboardEmpty.classList.add('hidden');
    try {
      const data = await apiRequest('/api/leaderboard');
      renderLeaderboard(data.leaderboard || []);
    } catch (error) {
      el.leaderboardBody.innerHTML = rowMessage(4, t('leaderboard.unavailable', { message: escapeHtml(error.message) }));
      showToast(t('toast.leaderboard', { message: error.message }), 'bad');
    }
  }

  function setActiveTab(tabName) {
    state.activeTab = tabName;
    el.tabButtons.forEach((button) => button.classList.toggle('active', button.dataset.tab === tabName));
    el.tabPanels.forEach((panel) => panel.classList.toggle('active', panel.id === tabName));
    if (tabName === 'home') {
      loadDashboard();
      loadIndex(state.indexRange);
      loadMovers();
    }
    if (tabName === 'market') loadSparklines();
    if (tabName === 'history') loadTransactions();
    if (tabName === 'leaderboard') loadLeaderboard();
    if (tabName === 'derivatives') loadPositions();
    if (tabName === 'portfolio') {
      if (state.portfolio) renderPortfolio(state.portfolio);
      loadEquityCurve();
      loadReport();
    }
  }

  function handleFilterClick(event) {
    const button = event.target.closest('[data-filter]');
    if (!button) return;
    setMarketFilter(button.dataset.filter);
    renderMarket();
  }

  function setMarketFilter(filter) {
    state.marketFilter = ['all', 'stock', 'crypto', 'fiat'].includes(filter) ? filter : 'all';
    el.assetFilters.querySelectorAll('.pill').forEach((pill) => {
      pill.classList.toggle('active', pill.dataset.filter === state.marketFilter);
    });
  }

  function openAddAssetModal() {
    resetAddAssetModal();
    el.addAssetModal.classList.remove('hidden');
    el.addAssetQuery.focus();
  }

  function closeAddAssetModal() {
    el.addAssetModal.classList.add('hidden');
  }

  function resetAddAssetModal() {
    state.addAssetSearchResults = [];
    el.addAssetForm.reset();
    setAddAssetClass(state.addAssetClass || 'stock');
    setStatus(el.addAssetMessage, '', '');
    renderAddAssetResults([]);
  }

  function handleAddAssetClassClick(event) {
    const button = event.target.closest('[data-add-class]');
    if (!button) return;
    setAddAssetClass(button.dataset.addClass);
  }

  function setAddAssetClass(assetClass) {
    const nextClass = ['stock', 'crypto', 'fiat'].includes(assetClass) ? assetClass : 'stock';
    state.addAssetClass = nextClass;
    state.addAssetSearchResults = [];
    el.addAssetClasses.querySelectorAll('[data-add-class]').forEach((button) => {
      button.classList.toggle('active', button.dataset.addClass === nextClass);
    });
    const copy = {
      stock: {
        label: t('addAsset.stockLabel'),
        placeholder: t('addAsset.stockPlaceholder'),
        help: t('addAsset.stockHelp'),
        submit: t('addAsset.stockSubmit'),
        showSearch: false
      },
      crypto: {
        label: t('addAsset.cryptoLabel'),
        placeholder: t('addAsset.cryptoPlaceholder'),
        help: t('addAsset.cryptoHelp'),
        submit: t('addAsset.cryptoSubmit'),
        showSearch: true
      },
      fiat: {
        label: t('addAsset.fiatLabel'),
        placeholder: t('addAsset.fiatPlaceholder'),
        help: t('addAsset.fiatHelp'),
        submit: t('addAsset.fiatSubmit'),
        showSearch: true
      }
    }[nextClass];
    el.addAssetQueryLabel.textContent = copy.label;
    el.addAssetQuery.placeholder = copy.placeholder;
    el.addAssetHelp.textContent = copy.help;
    el.addAssetSubmit.textContent = copy.submit;
    el.addAssetSubmit.classList.toggle('hidden', nextClass === 'crypto');
    el.addAssetSearch.classList.toggle('hidden', !copy.showSearch);
    renderAddAssetResults([]);
    setStatus(el.addAssetMessage, '', '');
  }

  function handleAddAssetQueryInput() {
    state.addAssetSearchResults = [];
    renderAddAssetResults([]);
    setStatus(el.addAssetMessage, '', '');
  }

  async function handleAddAssetSearch() {
    const assetClass = state.addAssetClass;
    const query = el.addAssetQuery.value.trim();
    if (!query) {
      setStatus(el.addAssetMessage, assetClass === 'fiat' ? t('addAsset.enterCurrency') : t('addAsset.enterSearch'), 'bad');
      return;
    }

    setAddAssetBusy(true, true);
    setStatus(el.addAssetMessage, t('addAsset.searching'), '');
    renderAddAssetResults([], t('addAsset.loadingResults'));
    try {
      const url = `/api/assets/search?class=${encodeURIComponent(assetClass)}&q=${encodeURIComponent(query)}`;
      const data = await apiRequest(url);
      const results = Array.isArray(data.results) ? data.results : [];
      state.addAssetSearchResults = results;
      if (results.length) {
        setStatus(el.addAssetMessage, results.length === 1
          ? t('addAsset.foundOne')
          : t('addAsset.foundMany', { count: results.length }), 'good');
      } else {
        setStatus(el.addAssetMessage, t('addAsset.noMatches'), '');
      }
      renderAddAssetResults(results);
    } catch (error) {
      state.addAssetSearchResults = [];
      renderAddAssetResults([]);
      setStatus(el.addAssetMessage, error.message, 'bad');
    } finally {
      setAddAssetBusy(false, true);
    }
  }

  async function handleAddAssetSubmit(event) {
    event.preventDefault();
    const assetClass = state.addAssetClass;
    if (assetClass === 'crypto') {
      setStatus(el.addAssetMessage, t('addAsset.pickCoin'), 'bad');
      return;
    }
    const symbol = normalizeAssetSymbol(el.addAssetQuery.value);
    if (!symbol) {
      setStatus(el.addAssetMessage, assetClass === 'fiat' ? t('addAsset.enterCurrencyCode') : t('addAsset.enterTicker'), 'bad');
      return;
    }
    const payload = assetClass === 'fiat'
      ? { asset_class: 'fiat', symbol, provider_id: symbol }
      : { asset_class: 'stock', symbol };
    await addCustomAsset(payload);
  }

  async function handleAddAssetResultClick(event) {
    const button = event.target.closest('[data-result-index]');
    if (!button) return;
    const result = state.addAssetSearchResults[Number(button.dataset.resultIndex)];
    if (!result) return;
    const assetClass = state.addAssetClass;
    const symbol = normalizeAssetSymbol(result.symbol);
    if (!symbol) {
      setStatus(el.addAssetMessage, t('addAsset.noSymbol'), 'bad');
      return;
    }
    const payload = {
      asset_class: assetClass,
      symbol,
      provider_id: result.provider_id || symbol,
      name: result.name || symbol
    };
    await addCustomAsset(payload);
  }

  async function addCustomAsset(payload) {
    setAddAssetBusy(true);
    setStatus(el.addAssetMessage, t('addAsset.adding', { symbol: payload.symbol }), '');
    try {
      const result = await apiRequest('/api/assets', {
        method: 'POST',
        body: JSON.stringify(payload)
      });
      const asset = result.asset || payload;
      showToast(t('addAsset.added', { symbol: asset.symbol || payload.symbol }), 'good');
      closeAddAssetModal();
      setMarketFilter(asset.asset_class || payload.asset_class);
      await loadAssets();
    } catch (error) {
      if (error.status === 401) return;
      setStatus(el.addAssetMessage, error.message, 'bad');
    } finally {
      setAddAssetBusy(false);
    }
  }

  function setAddAssetBusy(isBusy, searchOnly = false) {
    el.addAssetSearch.disabled = isBusy;
    if (!searchOnly) {
      el.addAssetSubmit.disabled = isBusy;
      el.addAssetQuery.disabled = isBusy;
      el.addAssetClasses.querySelectorAll('button').forEach((button) => {
        button.disabled = isBusy;
      });
      el.addAssetResults.querySelectorAll('button').forEach((button) => {
        button.disabled = isBusy;
      });
    }
  }

  function renderAddAssetResults(results, message = '') {
    if (message) {
      el.addAssetResults.classList.remove('hidden');
      el.addAssetResults.innerHTML = `<div class="search-result-empty">${escapeHtml(message)}</div>`;
      return;
    }
    if (!results.length) {
      el.addAssetResults.classList.add('hidden');
      el.addAssetResults.innerHTML = '';
      return;
    }
    el.addAssetResults.classList.remove('hidden');
    el.addAssetResults.innerHTML = results.map((result, index) => {
      const symbol = normalizeAssetSymbol(result.symbol);
      const name = result.name || '';
      return `<button class="search-result" type="button" data-result-index="${index}" role="option">
        <span class="symbol-cell">${escapeHtml(symbol)}</span>
        <span>${escapeHtml(name)}</span>
      </button>`;
    }).join('');
  }

  function normalizeAssetSymbol(value) {
    return String(value || '').trim().toUpperCase();
  }

  function renderMarket() {
    const filtered = state.assets.filter((asset) => state.marketFilter === 'all' || asset.asset_class === state.marketFilter);
    if (!filtered.length) {
      el.marketBody.innerHTML = rowMessage(5, t('market.noMatch'));
      return;
    }
    el.marketBody.innerHTML = filtered.map((asset) => {
      const tone = numberValue(asset.change_pct) >= 0 ? 'good' : 'bad';
      const spark = sparkSvg(state.sparklines[asset.symbol]);
      return `<tr>
        <td>${assetLabel(asset)}</td>
        <td class="num">${formatPrice(asset.price)}</td>
        <td class="num ${tone}">${formatPercent(asset.change_pct, true)}</td>
        <td>${spark || `<span class="spark-empty">—</span>`}</td>
        <td class="action-buttons">
          <button type="button" data-action="trade" data-symbol="${escapeAttr(asset.symbol)}" data-side="buy">${t('action.trade')}</button>
          <button type="button" data-action="chart" data-symbol="${escapeAttr(asset.symbol)}">${t('action.chart')}</button>
        </td>
      </tr>`;
    }).join('');
  }

  function renderSummary(portfolio) {
    el.summaryCash.textContent = formatMoney(portfolio.cash);
    el.summaryNetWorth.textContent = formatMoney(portfolio.net_worth);
    const tone = numberValue(portfolio.total_pl) >= 0 ? 'good' : 'bad';
    el.summaryPl.className = tone;
    el.summaryPl.textContent = `${formatMoney(portfolio.total_pl)} (${formatPercent(portfolio.total_pl_pct, true)})`;
  }

  function renderPortfolio(portfolio) {
    const positionsEquity = numberValue(portfolio.positions_equity);
    el.portfolioSummary.innerHTML = `
      <div class="summary-card"><span>${t('summary.cash')}</span><strong>${formatMoney(portfolio.cash)}</strong></div>
      <div class="summary-card"><span>${t('portfolio.holdings')}</span><strong>${formatMoney(portfolio.holdings_value)}</strong></div>
      <div class="summary-card"><span>${t('deriv.margin')}</span><strong>${formatMoney(portfolio.margin_locked)}${positionsEquity ? `<br><small class="${numberValue(portfolio.positions_pl) >= 0 ? 'good' : 'bad'}">${formatMoney(portfolio.positions_pl)}</small>` : ''}</strong></div>
      <div class="summary-card"><span>${t('summary.netWorth')}</span><strong>${formatMoney(portfolio.net_worth)}</strong></div>
      <div class="summary-card"><span>${t('summary.pl')}</span><strong class="${numberValue(portfolio.total_pl_pct) >= 0 ? 'good' : 'bad'}">${formatPercent(portfolio.total_pl_pct, true)}</strong></div>`;

    const holdings = Array.isArray(portfolio.holdings) ? portfolio.holdings : [];
    el.portfolioEmpty.classList.toggle('hidden', holdings.length > 0);
    if (!holdings.length) {
      el.holdingsBody.innerHTML = '';
      return;
    }

    el.holdingsBody.innerHTML = holdings.map((holding) => {
      const tone = numberValue(holding.pl) >= 0 ? 'good' : 'bad';
      const shortBadge = holding.is_short ? ` <span class="dir-badge short">${t('deriv.short')}</span>` : '';
      return `<tr>
        <td>${assetLabel(holding)}${shortBadge}</td>
        <td class="num">${formatQuantity(holding.quantity)}</td>
        <td class="num">${formatPrice(holding.avg_cost)}</td>
        <td class="num">${formatPrice(holding.price)}</td>
        <td class="num">${formatMoney(holding.value)}</td>
        <td class="num ${tone}">${formatMoney(holding.pl)}<br><small>${formatPercent(holding.pl_pct, true)}</small></td>
        <td class="action-buttons">
          <button type="button" data-action="trade" data-symbol="${escapeAttr(holding.symbol)}" data-side="sell">${t('trade.sell')}</button>
          <button type="button" data-action="chart" data-symbol="${escapeAttr(holding.symbol)}">${t('action.chart')}</button>
        </td>
      </tr>`;
    }).join('');
  }

  function renderPortfolioError(message) {
    if (!state.portfolio) {
      el.portfolioSummary.innerHTML = `<div class="empty-state">${t('portfolio.unavailable', { message: escapeHtml(message) })}</div>`;
      el.holdingsBody.innerHTML = '';
    }
  }

  function renderTransactions(transactions) {
    el.historyEmpty.classList.toggle('hidden', transactions.length > 0);
    if (!transactions.length) {
      el.historyBody.innerHTML = '';
      return;
    }
    el.historyBody.innerHTML = transactions.map((tx) => {
      const side = String(tx.side || '').toLowerCase();
      const tone = side === 'buy' ? 'buy' : 'sell';
      const sideLabel = side === 'buy' ? t('trade.buy') : side === 'sell' ? t('trade.sell') : (side || '?');
      return `<tr>
        <td>${formatDateTime(tx.ts)}</td>
        <td><span class="side-badge ${tone}">${escapeHtml(sideLabel)}</span></td>
        <td class="symbol-cell">${escapeHtml(tx.symbol)}</td>
        <td class="num">${formatQuantity(tx.quantity)}</td>
        <td class="num">${formatPrice(tx.price)}</td>
        <td class="num">${formatMoney(tx.total)}</td>
      </tr>`;
    }).join('');
  }

  function renderLeaderboard(rows) {
    el.leaderboardEmpty.classList.toggle('hidden', rows.length > 0);
    if (!rows.length) {
      el.leaderboardBody.innerHTML = '';
      return;
    }
    el.leaderboardBody.innerHTML = rows.map((row) => {
      const current = state.player && Number(row.player_id) === Number(state.player.id);
      const tone = numberValue(row.total_pl_pct) >= 0 ? 'good' : 'bad';
      return `<tr class="${current ? 'current-player' : ''}">
        <td class="rank-cell">#${escapeHtml(row.rank)}</td>
        <td>${escapeHtml(row.username)}${current ? ` <span class="you-badge">${t('leaderboard.you')}</span>` : ''}</td>
        <td class="num">${formatMoney(row.net_worth)}</td>
        <td class="num ${tone}">${formatPercent(row.total_pl_pct, true)}</td>
      </tr>`;
    }).join('');
  }

  function populateTradeSymbols() {
    const selected = el.tradeSymbol.value;
    el.tradeSymbol.innerHTML = state.assets.map((asset) => `<option value="${escapeAttr(asset.symbol)}">${escapeHtml(asset.symbol)} · ${escapeHtml(asset.name)}</option>`).join('');
    if (selected && state.assetBySymbol.has(selected)) el.tradeSymbol.value = selected;
  }

  function handleAssetAction(event) {
    const button = event.target.closest('[data-action]');
    if (!button) return;
    const symbol = button.dataset.symbol;
    if (button.dataset.action === 'trade') {
      openTradeModal(symbol, button.dataset.side || 'buy');
    } else if (button.dataset.action === 'chart') {
      openChartModal(symbol);
    }
  }

  function openTradeModal(symbol, side = 'buy') {
    if (!state.assets.length) {
      showToast(t('trade.marketNotLoaded'), 'bad');
      return;
    }
    populateTradeSymbols();
    el.tradeSymbol.value = symbol || state.assets[0].symbol;
    setTradeSide(side);
    el.tradeQuantity.value = '';
    el.tradeMessage.textContent = '';
    el.tradeMessage.className = 'form-status';
    el.tradeModal.classList.remove('hidden');
    updateTradeEstimate();
    el.tradeQuantity.focus();
  }

  function closeTradeModal() {
    el.tradeModal.classList.add('hidden');
  }

  function setTradeSide(side) {
    state.tradeSide = side === 'sell' ? 'sell' : 'buy';
    el.sideToggles.forEach((button) => button.classList.toggle('active', button.dataset.side === state.tradeSide));
    el.tradeSubmit.textContent = state.tradeSide === 'buy' ? t('trade.submitBuy') : t('trade.submitSell');
  }

  function updateTradeEstimate() {
    const asset = state.assetBySymbol.get(el.tradeSymbol.value);
    const quantity = Number.parseFloat(el.tradeQuantity.value);
    const total = asset && quantity > 0 ? asset.price * quantity : 0;
    if (asset) {
      el.tradeTitle.textContent = t(state.tradeSide === 'buy' ? 'trade.titleBuy' : 'trade.titleSell', { symbol: asset.symbol });
    } else {
      el.tradeTitle.textContent = t('trade.title');
    }
    el.tradeEstimate.textContent = formatMoney(total);
    el.tradePriceNote.textContent = asset
      ? t('trade.pricePer', { price: formatPrice(asset.price), symbol: asset.symbol })
      : t('trade.waitingPrice');
  }

  async function handleTradeSubmit(event) {
    event.preventDefault();
    const quantity = Number.parseFloat(el.tradeQuantity.value);
    const symbol = el.tradeSymbol.value;
    if (!symbol) {
      setStatus(el.tradeMessage, t('trade.chooseAsset'), 'bad');
      return;
    }
    if (!Number.isFinite(quantity) || quantity <= 0) {
      setStatus(el.tradeMessage, t('trade.quantityPositive'), 'bad');
      return;
    }

    el.tradeSubmit.disabled = true;
    setStatus(el.tradeMessage, t('trade.sending'), '');
    try {
      const result = await apiRequest('/api/trade', {
        method: 'POST',
        body: JSON.stringify({
          symbol,
          side: state.tradeSide,
          quantity
        })
      });
      setStatus(el.tradeMessage, result.message || t('trade.complete'), 'good');
      showToast(result.message || t('trade.complete'), 'good');
      await Promise.allSettled([loadPortfolio(), loadAssets(), loadTransactions(), loadLeaderboard()]);
    } catch (error) {
      if (error.status === 401) return;
      setStatus(el.tradeMessage, error.message, 'bad');
      showToast(error.message, 'bad');
    } finally {
      el.tradeSubmit.disabled = false;
    }
  }

  async function openChartModal(symbol) {
    state.chartSymbol = symbol;
    state.chartRange = '1mo';
    el.chartTitle.textContent = t('chart.titleFor', { symbol });
    el.chartModal.classList.remove('hidden');
    updateRangeButtons();
    await loadChart();
  }

  function closeChartModal() {
    el.chartModal.classList.add('hidden');
  }

  function handleRangeClick(event) {
    const button = event.target.closest('[data-range]');
    if (!button) return;
    state.chartRange = button.dataset.range;
    updateRangeButtons();
    loadChart();
  }

  function updateRangeButtons() {
    el.rangeButtons.querySelectorAll('.pill').forEach((button) => {
      button.classList.toggle('active', button.dataset.range === state.chartRange);
    });
  }

  async function loadChart() {
    if (!state.chartSymbol) return;
    setStatus(el.chartStatus, t('chart.loading'), '');
    try {
      const url = `/api/assets/${encodeURIComponent(state.chartSymbol)}/history?range=${encodeURIComponent(state.chartRange)}`;
      const data = await apiRequest(url);
      drawChart(data.points || []);
      setStatus(el.chartStatus, t('chart.meta', {
        symbol: state.chartSymbol,
        range: state.chartRange,
        count: data.points ? data.points.length : 0
      }), 'good');
    } catch (error) {
      setStatus(el.chartStatus, t('chart.unavailable', { message: error.message }), 'bad');
      showToast(t('toast.chart', { message: error.message }), 'bad');
    }
  }

  function drawChart(points) {
    if (!window.Chart) {
      setStatus(el.chartStatus, t('chart.jsUnavailable'), 'bad');
      return;
    }
    const labels = points.map((point) => new Date(point.t * 1000));
    const values = points.map((point) => Number(point.price));
    const first = values[0] || 0;
    const last = values[values.length - 1] || 0;
    const color = last >= first ? '#27f58a' : '#ff5c7a';
    const ctx = el.chartCanvas.getContext('2d');

    if (state.chart) state.chart.destroy();
    state.chart = new window.Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          label: t('chart.seriesLabel', { symbol: state.chartSymbol }),
          data: values,
          borderColor: color,
          backgroundColor: 'rgba(39, 245, 138, 0.12)',
          borderWidth: 2,
          tension: 0.25,
          pointRadius: values.length > 80 ? 0 : 2,
          fill: true
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              title: (items) => items[0] ? formatDateTime(items[0].label || labels[items[0].dataIndex] / 1000) : '',
              label: (item) => t('chart.tooltipPrice', { price: formatPrice(item.parsed.y) })
            }
          }
        },
        scales: {
          x: {
            ticks: {
              color: '#8ea0bd',
              maxTicksLimit: 6,
              callback: function tickLabel(value) {
                const date = this.getLabelForValue(value);
                return formatShortDate(date);
              }
            },
            grid: { color: 'rgba(142, 160, 189, 0.12)' }
          },
          y: {
            ticks: { color: '#8ea0bd', callback: (value) => formatCompactPrice(value) },
            grid: { color: 'rgba(142, 160, 189, 0.12)' }
          }
        }
      }
    });
  }

  // ---- Derivatives ----------------------------------------------------------

  async function loadDerivConfig() {
    if (state.deriv.config) return state.deriv.config;
    try {
      state.deriv.config = await apiRequest('/api/derivatives/config');
    } catch {
      state.deriv.config = { max_leverage: 20, default_leverage: 5 };
    }
    return state.deriv.config;
  }

  async function loadPositions() {
    if (!state.player) return;
    try {
      const data = await apiRequest(`/api/players/${encodeURIComponent(state.player.id)}/positions?include_closed=${state.deriv.showClosed}`);
      state.deriv.positions = data.positions || [];
      renderPositions();
      await loadFunding();
    } catch (error) {
      if (error.status === 401) return;
      setStatus(el.derivStatus, error.message, 'bad');
    }
  }

  async function loadFunding() {
    if (!state.player) return;
    try {
      const data = await apiRequest(`/api/players/${encodeURIComponent(state.player.id)}/funding`);
      state.deriv.funding = data.payments || [];
      renderFunding();
    } catch {
      // Funding history is informational; a failure should not block positions.
    }
  }

  function derivDirectionLabel(position) {
    // Derived locally so a language switch relabels instantly; the server's
    // direction_label is only a fallback for unknown values.
    if (position.direction === 'long') return t('deriv.long');
    if (position.direction === 'short') return t('deriv.short');
    return position.direction_label || position.direction || '';
  }

  function renderPositions() {
    const open = state.deriv.positions.filter((p) => p.is_open);
    const closed = state.deriv.positions.filter((p) => !p.is_open);

    el.derivEmpty.classList.toggle('hidden', open.length > 0);
    const margin = open.reduce((sum, p) => sum + numberValue(p.margin), 0);
    const unrealized = open.reduce((sum, p) => sum + numberValue(p.unrealized_pl) + numberValue(p.funding_paid), 0);
    const tone = unrealized >= 0 ? 'good' : 'bad';
    el.derivSummary.innerHTML = open.length ? `
      <div class="summary-card"><span>${t('deriv.summaryMargin')}</span><strong>${formatMoney(margin)}</strong></div>
      <div class="summary-card"><span>${t('deriv.summaryPl')}</span><strong class="${tone}">${formatMoney(unrealized)}</strong></div>
      <div class="summary-card"><span>${t('summary.netWorth')}</span><strong>${formatMoney(state.portfolio ? state.portfolio.net_worth : 0)}</strong></div>` : '';

    if (!open.length) {
      el.derivBody.innerHTML = '';
    } else {
      el.derivBody.innerHTML = open.map((p) => {
        const plTone = numberValue(p.unrealized_pl) >= 0 ? 'good' : 'bad';
        const ratio = numberValue(p.margin_ratio);
        const ratioClass = ratio <= 60 ? 'ratio-danger' : ratio <= 120 ? 'ratio-warn' : '';
        const dirClass = p.direction === 'long' ? 'long' : 'short';
        return `<tr>
          <td>
            <div class="deriv-detail">
              <span><span class="dir-badge ${dirClass}">${escapeHtml(derivDirectionLabel(p))}</span> ${escapeHtml(p.symbol)}</span>
              <small>${escapeHtml(p.kind === 'future' ? t('deriv.future') : t('deriv.perp'))} · ${numberValue(p.leverage)}x${p.kind === 'future' && p.expires_at ? ` · ${t('deriv.expires')} ${formatDateTime(p.expires_at)}` : ''}</small>
            </div>
          </td>
          <td class="num">${formatQuantity(p.size)}</td>
          <td class="num">${formatPrice(p.entry_price)}</td>
          <td class="num">${formatPrice(p.mark_price)}</td>
          <td class="num">${p.liquidation_price === null ? '—' : formatPrice(p.liquidation_price)}</td>
          <td class="num">${formatMoney(p.margin)}</td>
          <td class="num ${plTone}">${formatMoney(p.unrealized_pl)}<br><small>${formatPercent(p.unrealized_pl_pct, true)}</small></td>
          <td class="num ${ratioClass}">${formatPercent(p.margin_ratio, false)}</td>
          <td class="num">${formatMoney(p.funding_paid)}</td>
          <td class="action-buttons">
            <button type="button" data-deriv-action="close" data-id="${p.id}">${t('deriv.closePosition')}</button>
            <button type="button" data-deriv-action="margin" data-id="${p.id}" data-symbol="${escapeAttr(p.symbol)}">${t('deriv.addMargin')}</button>
          </td>
        </tr>`;
      }).join('');
    }

    el.derivClosedSection.classList.toggle('hidden', !state.deriv.showClosed);
    el.derivToggleClosed.textContent = state.deriv.showClosed ? t('deriv.hideClosed') : t('deriv.showClosed');
    if (state.deriv.showClosed) {
      el.derivClosedEmpty.classList.toggle('hidden', closed.length > 0);
      el.derivClosedBody.innerHTML = closed.map((p) => {
        const tone = numberValue(p.realized_pl) >= 0 ? 'good' : 'bad';
        const reason = p.close_reason === 'liquidated' ? t('deriv.statusLiquidated')
          : p.close_reason === 'expired' ? t('deriv.statusExpired')
          : t('deriv.reasonManual');
        const dirClass = p.direction === 'long' ? 'long' : 'short';
        return `<tr>
          <td><div class="deriv-detail">
            <span><span class="dir-badge ${dirClass}">${escapeHtml(derivDirectionLabel(p))}</span> ${escapeHtml(p.symbol)}</span>
            <small>${escapeHtml(reason)} · ${formatDateTime(p.closed_at)}</small>
          </div></td>
          <td class="num">${formatQuantity(p.size)}</td>
          <td class="num">${formatPrice(p.entry_price)}</td>
          <td class="num">${formatPrice(p.close_price)}</td>
          <td class="num">${formatMoney(p.margin)}</td>
          <td class="num ${tone}">${formatMoney(p.realized_pl)}<br><small>${formatPercent(p.realized_pl_pct, true)}</small></td>
        </tr>`;
      }).join('');
    } else {
      el.derivClosedBody.innerHTML = '';
    }
  }

  function renderFunding() {
    const rows = state.deriv.funding;
    el.derivFundingEmpty.classList.toggle('hidden', rows.length > 0);
    if (!rows.length) {
      el.derivFundingBody.innerHTML = '';
      return;
    }
    el.derivFundingBody.innerHTML = rows.map((row) => {
      const tone = numberValue(row.amount) >= 0 ? 'good' : 'bad';
      const dirClass = row.direction === 'long' ? 'long' : 'short';
      return `<tr>
        <td>${formatDateTime(row.ts)}</td>
        <td class="symbol-cell">${escapeHtml(row.symbol)}</td>
        <td><span class="dir-badge ${dirClass}">${escapeHtml(derivDirectionLabel(row))}</span></td>
        <td class="num ${tone}">${formatMoney(row.amount)}</td>
        <td class="num">${formatPrice(row.price)}</td>
      </tr>`;
    }).join('');
  }

  async function openDerivModal() {
    const config = await loadDerivConfig();
    if (!state.assets.length) {
      showToast(t('trade.marketNotLoaded'), 'bad');
      return;
    }
    // Uncapped: the input is a plain number field, and the hint explains the
    // only real ceiling (the minimum margin).
    el.derivLeverage.value = String(numberValue(config.default_leverage) || 10);
    populateDerivSymbols();
    el.derivSize.value = '';
    setStatus(el.derivMessage, '', '');
    setDerivDirection('long');
    setDerivKind('perp');
    el.derivModal.classList.remove('hidden');
    updateDerivEstimate();
    el.derivSize.focus();
  }

  function closeDerivModal() {
    el.derivModal.classList.add('hidden');
  }

  function populateDerivSymbols() {
    const selected = el.derivSymbol.value;
    el.derivSymbol.innerHTML = state.assets
      .map((asset) => `<option value="${escapeAttr(asset.symbol)}">${escapeHtml(asset.symbol)} · ${escapeHtml(asset.name)}</option>`)
      .join('');
    if (selected && state.assetBySymbol.has(selected)) el.derivSymbol.value = selected;
  }

  function setDerivDirection(direction) {
    state.deriv.direction = direction === 'short' ? 'short' : 'long';
    el.derivDirectionButtons.forEach((button) => {
      button.classList.toggle('active', button.dataset.derivDirection === state.deriv.direction);
    });
    updateDerivEstimate();
  }

  function setDerivKind(kind) {
    state.deriv.kind = kind === 'future' ? 'future' : 'perp';
    el.derivKindButtons.forEach((button) => {
      button.classList.toggle('active', button.dataset.derivKind === state.deriv.kind);
    });
    const config = state.deriv.config || {};
    if (state.deriv.kind === 'future') {
      const minutes = Math.round(numberValue(config.future_duration_seconds || 3600) / 60);
      el.derivKindNote.textContent = t('deriv.future') + ' · ' + t('deriv.expires') + ' ' + minutes + ' min';
    } else {
      const minutes = Math.round(numberValue(config.funding_interval_seconds || 300) / 60);
      el.derivKindNote.textContent = t('deriv.ratePerInterval', { rate: formatPercent(numberValue(config.funding_rate_cap || 0) * 100, false), minutes });
    }
    updateDerivEstimate();
  }

  function updateDerivEstimate() {
    const asset = state.assetBySymbol.get(el.derivSymbol.value);
    const size = Number.parseFloat(el.derivSize.value);
    const lev = Math.max(1, Number.parseFloat(el.derivLeverage.value) || 1);

    if (!asset) {
      el.derivNotional.textContent = formatMoney(0);
      el.derivMarginEst.textContent = '';
      el.derivLiqEst.textContent = '';
      el.derivFundingEst.textContent = '';
      return;
    }

    const config = state.deriv.config || {};
    const mult = numberValue((config.contract_multipliers || {})[asset.asset_class] || 1) || 1;
    const notional = size > 0 ? size * asset.price * mult : 0;
    const margin = notional / lev;

    el.derivNotional.textContent = formatMoney(notional);
    el.derivMarginEst.textContent = `${t('deriv.marginNeeded')}: ${formatMoney(margin)}`;

    if (notional > 0) {
      // Mirror the server's formula so the number shown matches what it will do.
      const maint = numberValue(config.maintenance_margin_pct || 0) / 100;
      const perUnit = size * mult;
      const distance = (margin * (1 - maint)) / perUnit;
      const liq = state.deriv.direction === 'long' ? asset.price - distance : asset.price + distance;
      el.derivLiqEst.textContent = `${t('deriv.liqPrice')}: ${formatPrice(Math.max(liq, 0))}`;
      // How far the price has to move before the whole margin is gone. At high
      // leverage this is the number that matters: 0.05% is one bad tick.
      const wipePct = asset.price > 0 ? (distance / asset.price) * 100 : 0;
      const danger = wipePct <= 1;
      el.derivLeverageHint.textContent = t('deriv.wipeDistance', { pct: wipePct.toFixed(4) })
        + (danger ? ' ' + t('deriv.wipeDanger') : '');
      el.derivLeverageHint.className = danger ? 'auth-note bad' : 'auth-note';
    } else {
      el.derivLiqEst.textContent = '';
      el.derivLeverageHint.textContent = '';
      el.derivLeverageHint.className = 'auth-note';
    }

    if (state.deriv.kind === 'perp') {
      el.derivFundingEst.textContent = t('deriv.funding') + ': ' + formatPercent(numberValue(config.funding_rate_cap || 0) * 100, false) + ' max';
    } else {
      el.derivFundingEst.textContent = '';
    }
  }

  function handleLeveragePreset(event) {
    const button = event.target.closest('[data-leverage-preset]');
    if (!button) return;
    el.derivLeverage.value = button.dataset.leveragePreset;
    updateDerivEstimate();
  }

  async function handleDerivSubmit(event) {
    event.preventDefault();
    const symbol = el.derivSymbol.value;
    const size = Number.parseFloat(el.derivSize.value);
    const leverage = Number.parseFloat(el.derivLeverage.value);
    if (!symbol) {
      setStatus(el.derivMessage, t('trade.chooseAsset'), 'bad');
      return;
    }
    if (!Number.isFinite(size) || size <= 0) {
      setStatus(el.derivMessage, t('trade.quantityPositive'), 'bad');
      return;
    }

    el.derivSubmit.disabled = true;
    setStatus(el.derivMessage, t('deriv.opening'), '');
    try {
      const result = await apiRequest('/api/positions', {
        method: 'POST',
        body: JSON.stringify({
          symbol,
          kind: state.deriv.kind,
          direction: state.deriv.direction,
          size,
          leverage
        })
      });
      showToast(result.message || t('deriv.complete'), 'good');
      setStatus(el.derivMessage, result.message || '', 'good');
      closeDerivModal();
      await Promise.allSettled([loadPositions(), loadPortfolio()]);
    } catch (error) {
      if (error.status === 401) return;
      setStatus(el.derivMessage, error.message, 'bad');
      showToast(error.message, 'bad');
    } finally {
      el.derivSubmit.disabled = false;
    }
  }

  function handleDerivAction(event) {
    const button = event.target.closest('[data-deriv-action]');
    if (!button) return;
    const id = Number(button.dataset.id);
    if (button.dataset.derivAction === 'close') {
      closePositionById(id);
    } else if (button.dataset.derivAction === 'margin') {
      openMarginModal(id, button.dataset.symbol || '');
    }
  }

  async function closePositionById(positionId) {
    setStatus(el.derivStatus, t('deriv.closing'), '');
    try {
      const result = await apiRequest(`/api/positions/${positionId}/close`, { method: 'POST' });
      setStatus(el.derivStatus, result.message || '', 'good');
      showToast(result.message || '', 'good');
      await Promise.allSettled([loadPositions(), loadPortfolio()]);
    } catch (error) {
      if (error.status === 401) return;
      setStatus(el.derivStatus, error.message, 'bad');
      showToast(error.message, 'bad');
    }
  }

  function openMarginModal(positionId, symbol) {
    state.deriv.marginTarget = positionId;
    el.marginTitle.textContent = t('deriv.addMarginTitle', { symbol });
    el.marginAmount.value = '';
    setStatus(el.marginMessage, '', '');
    el.marginModal.classList.remove('hidden');
    el.marginAmount.focus();
  }

  function closeMarginModal() {
    state.deriv.marginTarget = null;
    el.marginModal.classList.add('hidden');
  }

  async function handleMarginSubmit(event) {
    event.preventDefault();
    const amount = Number.parseFloat(el.marginAmount.value);
    const target = state.deriv.marginTarget;
    if (!target) return;
    if (!Number.isFinite(amount) || amount <= 0) {
      setStatus(el.marginMessage, t('deriv.badAmount'), 'bad');
      return;
    }

    el.marginSubmit.disabled = true;
    setStatus(el.marginMessage, '', '');
    try {
      const result = await apiRequest(`/api/positions/${target}/margin`, {
        method: 'POST',
        body: JSON.stringify({ amount })
      });
      showToast(result.message || '', 'good');
      closeMarginModal();
      await Promise.allSettled([loadPositions(), loadPortfolio()]);
    } catch (error) {
      if (error.status === 401) return;
      setStatus(el.marginMessage, error.message, 'bad');
      showToast(error.message, 'bad');
    } finally {
      el.marginSubmit.disabled = false;
    }
  }

  async function toggleClosedPositions() {
    state.deriv.showClosed = !state.deriv.showClosed;
    await loadPositions();
  }

  // ---- Dashboard -----------------------------------------------------------

  function renderSeason(season) {
    if (!season) {
      el.seasonName.textContent = '—';
      el.seasonCountdown.textContent = t('home.seasonEnded');
      el.seasonProgressFill.style.width = '0%';
      return;
    }
    el.seasonName.textContent = season.name;
    const left = numberValue(season.seconds_left);
    el.seasonCountdown.textContent = left > 0
      ? t('home.seasonEnds', { time: formatDuration(left) })
      : t('home.seasonEnded');
    const total = Math.max(1, numberValue(season.ends_at) - numberValue(season.starts_at));
    const elapsed = Math.min(total, Math.max(0, total - left));
    el.seasonProgressFill.style.width = `${(elapsed / total) * 100}%`;
  }

  function formatDuration(seconds) {
    const s = Math.max(0, Math.floor(numberValue(seconds)));
    const d = Math.floor(s / 86400);
    const h = Math.floor((s % 86400) / 3600);
    const m = Math.floor((s % 3600) / 60);
    if (d > 0) return `${d}d ${h}h`;
    if (h > 0) return `${h}h ${m}m`;
    return `${m}m`;
  }

  async function loadDashboard() {
    try {
      const data = await apiRequest('/api/dashboard');
      renderSeason(data.season);
      renderIndex(data.index);
      renderFeed(data.feed || []);
      renderHomeStandings(data.leaderboard || []);
    } catch (error) {
      if (error.status === 401) return;
      setStatus(el.indexValue, '—', '');
    }
  }

  async function loadIndex(range) {
    const hours = numberValue(range || state.indexRange) || 24;
    state.indexRange = hours;
    try {
      const data = await apiRequest(`/api/index/series?hours=${hours}&points=180`);
      drawIndexChart(data.series || []);
    } catch {
      // Keep the previous chart rather than blanking it on a transient failure.
    }
  }

  function renderIndex(index) {
    if (!index) return;
    const quote = index.value;
    if (quote) {
      el.indexValue.textContent = numberValue(quote.value).toLocaleString(locale(), {
        minimumFractionDigits: 2, maximumFractionDigits: 2
      });
      setStatus(el.indexChange, formatPercent(quote.change_pct, true),
        numberValue(quote.change_pct) >= 0 ? 'good' : 'bad');
    }
    drawIndexChart(index.series || []);
    el.indexTitle.textContent = t('home.indexEyebrow');
  }

  function drawIndexChart(series) {
    if (!window.Chart) return;
    const ctx = el.indexChart.getContext('2d');
    const labels = series.map((p) => new Date(p.t * 1000));
    const values = series.map((p) => Number(p.v));
    const first = values[0] || 0;
    const last = values[values.length - 1] || 0;
    const up = last >= first;
    const color = up ? '#27f58a' : '#ff5c7a';

    if (state.indexChartInstance) state.indexChartInstance.destroy();
    state.indexChartInstance = new window.Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          label: t('home.indexEyebrow'),
          data: values,
          borderColor: color,
          backgroundColor: up ? 'rgba(39, 245, 138, 0.12)' : 'rgba(255, 92, 122, 0.12)',
          borderWidth: 2,
          tension: 0.25,
          pointRadius: 0,
          fill: true
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              title: (items) => (items[0] ? formatDateTime(items[0].label) : ''),
              label: (item) => item.parsed.y.toFixed(2)
            }
          }
        },
        scales: {
          x: {
            ticks: { color: '#8ea0bd', maxTicksLimit: 6, callback: function cb(v) { return formatShortTime(this.getLabelForValue(v)); } },
            grid: { color: 'rgba(142, 160, 189, 0.1)' }
          },
          y: {
            ticks: { color: '#8ea0bd', callback: (v) => Number(v).toFixed(0) },
            grid: { color: 'rgba(142, 160, 189, 0.1)' }
          }
        }
      }
    });
  }

  function renderFeed(events) {
    if (!events.length) {
      el.activityFeed.innerHTML = `<div class="feed-empty">${escapeHtml(t('home.emptyFeed'))}</div>`;
      return;
    }
    // Only rebuild when something new arrived, otherwise the poll would restart
    // the entry animation every few seconds.
    const newest = events[0] ? events[0].id : 0;
    if (newest === state.feedNewestId && el.activityFeed.dataset.size === String(events.length)) {
      return;
    }
    state.feedNewestId = newest;
    el.activityFeed.dataset.size = String(events.length);
    el.activityFeed.innerHTML = events.slice(0, 40).map((event) => {
      const tone = eventTone(event);
      return `<div class="feed-item ${tone}">
        <span class="feed-time">${escapeHtml(formatTime(event.ts))}</span>
        <span>${eventText(event)}</span>
      </div>`;
    }).join('');
  }

  function eventTone(event) {
    if (event.kind === 'liquidation') return 'sev-alert';
    if (event.kind === 'season_end') return 'sev-good';
    return '';
  }

  function eventText(event) {
    const d = event.detail || {};
    const name = escapeHtml(event.username || '—');
    const amount = formatMoney(event.amount || 0);
    switch (event.kind) {
      case 'trade': {
        const key = d.short ? 'event.tradeShort' : 'event.trade';
        const side = d.side === 'buy' ? t('trade.buy') : t('trade.sell');
        return t(key, {
          name,
          side,
          quantity: formatQuantity(d.quantity),
          symbol: escapeHtml(event.symbol || ''),
          price: formatPrice(d.price)
        });
      }
      case 'position_open': {
        const direction = d.direction === 'short' ? t('deriv.short') : t('deriv.long');
        // Spot shorts carry no leverage; rendering "0x" would be nonsense.
        const leverage = numberValue(d.leverage);
        return leverage > 0
          ? t('event.positionOpen', {
              name, direction,
              size: formatQuantity(d.size),
              symbol: escapeHtml(event.symbol || ''),
              leverage
            })
          : t('event.positionOpenSpot', {
              name, direction,
              size: formatQuantity(d.size),
              symbol: escapeHtml(event.symbol || '')
            });
      }
      case 'position_close':
        return t('event.positionClose', {
          name, symbol: escapeHtml(event.symbol || ''), amount
        });
      case 'liquidation':
        return t('event.liquidation', {
          name, symbol: escapeHtml(event.symbol || ''), amount
        });
      case 'future_settle':
        return t('event.futureSettle', {
          name, symbol: escapeHtml(event.symbol || ''), price: formatPrice(d.close_price)
        });
      case 'season_start':
        return t('event.seasonStart', { name: escapeHtml(d.name || '') });
      case 'season_end':
        return t('event.seasonEnd', {
          name: escapeHtml(d.name || ''),
          winner: escapeHtml(d.winner || '—'),
          return: formatPercent(d.winner_return_pct, true)
        });
      case 'margin_warning':
        return t('event.marginWarning', { symbol: escapeHtml(event.symbol || '') });
      default:
        return `${escapeHtml(event.kind)}${event.symbol ? ' · ' + escapeHtml(event.symbol) : ''}`;
    }
  }

  function renderHomeStandings(rows) {
    if (!rows.length) {
      el.homeStandings.innerHTML = `<div class="feed-empty">${escapeHtml(t('home.emptyStandings'))}</div>`;
      return;
    }
    el.homeStandings.innerHTML = rows.slice(0, 8).map((row) => {
      const me = state.player && Number(row.player_id) === Number(state.player.id);
      return `<div class="standings-row ${me ? 'me' : ''}">
        <span class="standings-rank">#${escapeHtml(row.rank)}</span>
        <span class="standings-name">${escapeHtml(row.username)}</span>
        <span class="standings-worth">${formatMoney(row.net_worth)}</span>
        <span class="${numberValue(row.total_pl_pct) >= 0 ? 'good' : 'bad'}">${formatPercent(row.total_pl_pct, true)}</span>
      </div>`;
    }).join('');
  }

  async function loadMovers() {
    // Movers describe the whole board, so the home tab needs the market payload
    // even if the user never visited the market tab.
    if (!state.assets.length) {
      try {
        const data = await apiRequest('/api/assets');
        state.assets = Array.isArray(data.assets) ? data.assets : [];
        state.assetBySymbol = new Map(state.assets.map((asset) => [asset.symbol, asset]));
      } catch {
        return;
      }
    }
    const sorted = [...state.assets]
      .filter((a) => a.asset_class !== 'fiat')
      .sort((a, b) => numberValue(b.change_pct) - numberValue(a.change_pct));
    const picks = sorted.slice(0, 4).concat(sorted.slice(-4).reverse());
    el.movers.innerHTML = picks.map((asset) => {
      const tone = numberValue(asset.change_pct) >= 0 ? 'good' : 'bad';
      return `<div class="mover">
        <span class="mover-symbol">${escapeHtml(asset.symbol)}</span>
        <span class="mover-price">${formatPrice(asset.price)}</span>
        <span class="mover-change ${tone}">${formatPercent(asset.change_pct, true)}</span>
      </div>`;
    }).join('');
  }

  async function loadSparklines() {
    try {
      const data = await apiRequest('/api/sparklines?hours=24&points=30');
      state.sparklines = data.sparklines || {};
      if (state.activeTab === 'market') renderMarket();
    } catch {
      // Sparklines are decoration; keep the table usable without them.
    }
  }

  function sparkSvg(values) {
    if (!values || values.length < 2) return '';
    const min = Math.min(...values);
    const max = Math.max(...values);
    const span = max - min || 1;
    const w = 92;
    const h = 26;
    const step = w / (values.length - 1);
    const points = values.map((v, i) => `${(i * step).toFixed(1)},${(h - ((v - min) / span) * (h - 4) - 2).toFixed(1)}`).join(' ');
    const color = values[values.length - 1] >= values[0] ? '#27f58a' : '#ff5c7a';
    return `<svg class="spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><polyline points="${points}" fill="none" stroke="${color}" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round"/></svg>`;
  }

  // ---- Alerts --------------------------------------------------------------

  async function loadAlerts() {
    if (!state.player) return;
    try {
      const data = await apiRequest('/api/alerts');
      state.alerts = data.alerts || [];
      renderAlerts();
    } catch {
      // The bell is optional; never surface an error for it.
    }
  }

  function renderAlerts() {
    const count = state.alerts.length;
    if (count > 0) {
      el.alertCount.textContent = String(count);
      el.alertCount.classList.remove('hidden');
    } else {
      el.alertCount.classList.add('hidden');
    }
    if (!state.alertPanelOpen) return;
    if (!count) {
      el.alertList.innerHTML = `<div class="feed-empty">${escapeHtml(t('alerts.empty'))}</div>`;
      return;
    }
    el.alertList.innerHTML = state.alerts.map((alert) => {
      const d = alert.detail || {};
      let text;
      let tone = '';
      if (alert.kind === 'liquidation') {
        tone = 'danger';
        text = t('alerts.liquidated', {
          symbol: escapeHtml(alert.symbol || ''),
          amount: formatMoney(Math.abs(numberValue(alert.amount)))
        });
      } else if (alert.kind === 'margin_warning') {
        text = t('alerts.marginWarning', {
          symbol: escapeHtml(alert.symbol || ''),
          ratio: numberValue(d.margin_ratio).toFixed(1),
          liq: d.liquidation_price === null || d.liquidation_price === undefined
            ? '—' : formatPrice(d.liquidation_price)
        });
      } else if (alert.kind === 'future_settle') {
        text = t('alerts.futureSettled', {
          symbol: escapeHtml(alert.symbol || ''),
          amount: formatMoney(numberValue(alert.amount))
        });
      } else if (alert.kind === 'overtake') {
        text = t('alerts.overtaken', { name: escapeHtml(d.by || '—') });
      } else {
        text = `${escapeHtml(alert.kind)} ${escapeHtml(alert.symbol || '')}`;
      }
      return `<div class="alert-item ${tone}">${text}<span class="alert-time">${escapeHtml(formatDateTime(alert.ts))}</span></div>`;
    }).join('');
  }

  function toggleAlertPanel() {
    state.alertPanelOpen = !state.alertPanelOpen;
    el.alertPanel.classList.toggle('hidden', !state.alertPanelOpen);
    if (state.alertPanelOpen) renderAlerts();
  }

  // ---- Reports -------------------------------------------------------------

  async function loadEquityCurve() {
    if (!state.player) return;
    try {
      const data = await apiRequest(`/api/players/${encodeURIComponent(state.player.id)}/equity?hours=${state.equityRange}`);
      drawEquityChart(data.series || []);
    } catch {
      // Leave the previous curve in place.
    }
  }

  function drawEquityChart(series) {
    if (!window.Chart) return;
    const ctx = el.equityChart.getContext('2d');
    const labels = series.map((p) => new Date(p.t * 1000));
    const values = series.map((p) => Number(p.v));
    const first = values[0] || 0;
    const last = values[values.length - 1] || 0;
    const up = last >= first;
    const color = up ? '#27f58a' : '#ff5c7a';

    if (state.equityChartInstance) state.equityChartInstance.destroy();
    state.equityChartInstance = new window.Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          label: t('report.equity'),
          data: values,
          borderColor: color,
          backgroundColor: up ? 'rgba(39, 245, 138, 0.12)' : 'rgba(255, 92, 122, 0.12)',
          borderWidth: 2,
          tension: 0.25,
          pointRadius: 0,
          fill: true
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              title: (items) => (items[0] ? formatDateTime(items[0].label) : ''),
              label: (item) => formatMoney(item.parsed.y)
            }
          }
        },
        scales: {
          x: {
            ticks: { color: '#8ea0bd', maxTicksLimit: 5, callback: function cb(v) { return formatShortTime(this.getLabelForValue(v)); } },
            grid: { color: 'rgba(142, 160, 189, 0.1)' }
          },
          y: {
            ticks: { color: '#8ea0bd', callback: (v) => formatCompactPrice(v) },
            grid: { color: 'rgba(142, 160, 189, 0.1)' }
          }
        }
      }
    });
  }

  async function loadReport() {
    if (!state.player) return;
    try {
      const report = await apiRequest(`/api/players/${encodeURIComponent(state.player.id)}/report?hours=24`);
      renderReport(report);
    } catch {
      el.dailyReport.innerHTML = '';
    }
  }

  function renderReport(report) {
    if (!report || !report.has_data) {
      el.dailyReport.innerHTML = `<div class="report-empty">${escapeHtml(t('report.noData'))}</div>`;
      return;
    }
    const tone = numberValue(report.change) >= 0 ? 'good' : 'bad';
    const rows = [
      [t('report.start'), formatMoney(report.start_net_worth)],
      [t('report.end'), formatMoney(report.end_net_worth)],
      [t('report.change'), `<span class="${tone}">${formatMoney(report.change)} (${formatPercent(report.change_pct, true)})</span>`],
      [t('report.high'), formatMoney(report.high)],
      [t('report.low'), formatMoney(report.low)],
      [t('report.trades'), String(numberValue(report.trades))],
      [t('report.opened'), String(numberValue(report.positions_opened))],
      [t('report.liquidations'), String(numberValue(report.liquidations))]
    ];
    if (report.best_symbol) {
      rows.push([t('report.best'), `${escapeHtml(report.best_symbol.symbol)} ${formatPercent(report.best_symbol.change_pct, true)}`]);
    }
    if (report.worst_symbol) {
      rows.push([t('report.worst'), `${escapeHtml(report.worst_symbol.symbol)} ${formatPercent(report.worst_symbol.change_pct, true)}`]);
    }
    el.dailyReport.innerHTML = rows
      .map(([label, value]) => `<div class="report-row"><span>${label}</span><strong>${value}</strong></div>`)
      .join('') + `<div class="report-row"><span>${escapeHtml(t('report.points', { count: numberValue(report.points) }))}</span></div>`;
  }

  async function apiRequest(path, options = {}) {    const headers = { ...(options.headers || {}) };
    const method = String(options.method || 'GET').toUpperCase();
    if ((options.body || method === 'POST') && !headers['Content-Type']) headers['Content-Type'] = 'application/json';
    if (state.auth && state.auth.token && !headers.Authorization) headers.Authorization = `Bearer ${state.auth.token}`;
    // Server-side messages (trade receipts, validation errors) follow the UI language.
    if (!headers['Accept-Language']) headers['Accept-Language'] = locale();
    const response = await fetch(path, { ...options, headers });
    let data = null;
    try {
      data = await response.json();
    } catch {
      data = null;
    }
    if (!response.ok) {
      const message = data && (data.message || data.detail) ? (data.message || data.detail) : t('request.failed', { status: response.status });
      const error = new Error(message);
      error.status = response.status;
      error.data = data;
      if (response.status === 401 && shouldExpireSession(path)) {
        handleSessionExpired();
      }
      throw error;
    }
    return data || {};
  }

  function shouldExpireSession(path) {
    const publicAuthPaths = ['/api/login', '/api/register', '/api/recover'];
    return Boolean(state.auth && state.auth.token && !publicAuthPaths.includes(path));
  }

  function showToast(message, tone = '') {
    const toast = document.createElement('div');
    toast.className = `toast ${tone}`.trim();
    toast.innerHTML = `<span>${escapeHtml(message)}</span><button type="button" aria-label="${escapeAttr(t('toast.dismiss'))}">×</button>`;
    toast.querySelector('button').addEventListener('click', () => toast.remove());
    el.toastRegion.appendChild(toast);
    window.setTimeout(() => toast.remove(), tone === 'bad' ? 7000 : 4500);
  }

  function setStatus(node, message, tone) {
    node.textContent = message;
    node.className = `${node.className.split(' ')[0]} ${tone || ''}`.trim();
  }

  function assetLabel(asset) {
    const klass = asset.asset_class || '';
    const customBadge = asset.custom === true ? ` <span class="custom-badge">${t('asset.custom')}</span>` : '';
    const classLabel = klass === 'stock' ? t('market.stocks')
      : klass === 'crypto' ? t('market.crypto')
      : klass === 'fiat' ? t('market.fiat')
      : klass.toUpperCase();
    return `<div class="asset-label"><span class="symbol-cell">${escapeHtml(asset.symbol)}${customBadge}</span><span>${escapeHtml(asset.name || '')}</span><small>${escapeHtml(classLabel)}</small></div>`;
  }

  function rowLoading(colspan, message) {
    return rowMessage(colspan, `<span class="loader"></span>${escapeHtml(message)}`);
  }

  function rowMessage(colspan, message) {
    return `<tr><td colspan="${colspan}" class="table-message">${message}</td></tr>`;
  }

  function numberValue(value) {
    const number = Number(value);
    return Number.isFinite(number) ? number : 0;
  }

  function formatMoney(value) {
    return numberValue(value).toLocaleString(locale(), {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    });
  }

  function formatPrice(value) {
    const number = numberValue(value);
    const abs = Math.abs(number);
    if (abs >= 1000) return formatMoney(number);
    if (abs >= 1) {
      return `$${number.toLocaleString(locale(), { minimumFractionDigits: 2, maximumFractionDigits: 4 })}`;
    }
    return `$${number.toLocaleString(locale(), { minimumFractionDigits: 0, maximumSignificantDigits: 6 })}`;
  }

  function formatCompactPrice(value) {
    const number = numberValue(value);
    if (Math.abs(number) >= 1000) return `$${Math.round(number).toLocaleString(locale())}`;
    return formatPrice(number);
  }

  function formatQuantity(value) {
    return numberValue(value).toLocaleString(locale(), { maximumFractionDigits: 8 });
  }

  function formatPercent(value, signed = false) {
    const number = numberValue(value);
    const sign = signed && number > 0 ? '+' : '';
    return `${sign}${number.toLocaleString(locale(), { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`;
  }

  function formatTime(ts) {
    if (!ts) return t('time.now');
    return new Date(ts * 1000).toLocaleTimeString(locale(), { hour: '2-digit', minute: '2-digit' });
  }

  function formatDateTime(ts) {
    const date = typeof ts === 'number' ? new Date(ts * 1000) : new Date(ts);
    if (Number.isNaN(date.getTime())) return t('time.unknown');
    return date.toLocaleString(locale(), { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  }

  function handleIndexRange(event) {
    const button = event.target.closest('[data-index-range]');
    if (!button) return;
    state.indexRange = Number(button.dataset.indexRange) || 24;
    el.indexRanges.querySelectorAll('.pill').forEach((pill) => {
      pill.classList.toggle('active', Number(pill.dataset.indexRange) === state.indexRange);
    });
    loadIndex(state.indexRange);
  }

  function handleEquityRange(event) {
    const button = event.target.closest('[data-equity-range]');
    if (!button) return;
    state.equityRange = Number(button.dataset.equityRange) || 24;
    el.equityRanges.querySelectorAll('.pill').forEach((pill) => {
      pill.classList.toggle('active', Number(pill.dataset.equityRange) === state.equityRange);
    });
    loadEquityCurve();
  }

  function formatShortTime(value) {
    const date = value instanceof Date ? value : new Date(value);
    if (Number.isNaN(date.getTime())) return '';
    return date.toLocaleTimeString(locale(), { hour: '2-digit', minute: '2-digit' });
  }

  function formatShortDate(value) {
    const date = value instanceof Date ? value : new Date(value);
    if (Number.isNaN(date.getTime())) return '';
    return date.toLocaleDateString(locale(), { month: 'short', day: 'numeric' });
  }

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>'"]/g, (char) => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      "'": '&#39;',
      '"': '&quot;'
    }[char]));
  }

  function escapeAttr(value) {
    return escapeHtml(value);
  }
})();
