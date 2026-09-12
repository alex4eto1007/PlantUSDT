// PlantUSDT Mini App - JavaScript (Polygon Network)

const API_BASE = 'https://plantusdt.ddns.net';
window.API_BASE = API_BASE;

let tg = window.Telegram.WebApp;
let tgUser = tg.initDataUnsafe ? tg.initDataUnsafe.user : null;
const PROJECT_WALLET = '0x6b2672E8b8A3D610AD3C148C70627f3b79D5cF76';
const NETWORK = 'Polygon';
const USDT_CONTRACT = '0xc2132D05D31c914a87C6611C10748AEb04B58e8F';
let timerInterval = null;
let lastAdTime = 0;
const AD_COOLDOWN = 5000;
let interstitialAdsDisabled = false;
let isLoading = false;
let isDataLoaded = false;
window.selectedCurrency = window.selectedCurrency || 'usdt';

window._latestAdCount = null;
window._adCountTimestamp = null;
window._isBanned = false;

// ============================================
// BAN SCREEN
// ============================================
function showBanScreen(reason) {
    if (window._isBanned) return;
    window._isBanned = true;
    try {
        if (timerInterval) { clearInterval(timerInterval); timerInterval = null; }
    } catch (e) {}
    var ids = ['appContent','loadingMessage','fieldsContainer','dashboardStats','historyList'];
    ids.forEach(function(id) { var el = document.getElementById(id); if (el) el.style.display = 'none'; });
    var banOverlay = document.createElement('div');
    banOverlay.id = 'banScreen';
    banOverlay.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;background:#0a0e17;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:32px 24px;text-align:center;z-index:999999;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;color:#ccd6f0;';
    banOverlay.innerHTML = '<div style="font-size:72px;margin-bottom:16px;line-height:1;">🚫</div>' +
        '<div style="font-size:24px;font-weight:800;color:#ff6b6b;margin-bottom:12px;letter-spacing:0.5px;">Account Suspended</div>' +
        '<div style="font-size:15px;color:#8892b0;line-height:1.7;max-width:360px;margin-bottom:28px;">' +
        'Your PlantUSDT account has been suspended.<br><br>' +
        (reason ? '<em style="color:#ffd93d;">' + reason + '</em><br><br>' : '') +
        'If you believe this is a mistake, please contact support.</div>' +
        '<a href="https://t.me/Alex_PlantUSDT" target="_blank" style="display:inline-block;padding:14px 28px;background:linear-gradient(135deg,#00d4ff,#0088ff);color:#fff;text-decoration:none;border-radius:12px;font-weight:700;font-size:15px;box-shadow:0 4px 20px rgba(0,136,255,0.3);">💬 Contact Support</a>' +
        '<div style="margin-top:32px;font-size:12px;color:#495670;">🟣 PlantUSDT · Polygon Network</div>';
    document.body.appendChild(banOverlay);
    console.log('🚫 Ban screen displayed');
}

// ============================================
// GRAM (TON) ADDRESS VALIDATION
// ============================================
function isValidTonAddress(address) {
    if (!address) return false;
    return /^(UQ|EQ)[A-Za-z0-9_-]{46}$/.test(address) || /^-?\d+:[a-fA-F0-9]{64}$/.test(address);
}

// ============================================
// MATH CAPTCHA
// ============================================
let mathCaptchaAnswer = null;
let mathCaptchaQuestion = null;
let pendingAdCallback = null;

function generateMathCaptcha() {
    const num1 = Math.floor(Math.random() * 10) + 1;
    const num2 = Math.floor(Math.random() * 10) + 1;
    const operators = ['+', '-'];
    const op = operators[Math.floor(Math.random() * operators.length)];
    let answer, question;
    if (op === '+') {
        answer = num1 + num2;
        question = `${num1} + ${num2} = ?`;
    } else {
        const bigger = Math.max(num1, num2);
        const smaller = Math.min(num1, num2);
        answer = bigger - smaller;
        question = `${bigger} - ${smaller} = ?`;
    }
    mathCaptchaQuestion = question;
    mathCaptchaAnswer = answer;
    return { question: mathCaptchaQuestion, answer: mathCaptchaAnswer };
}

// ============================================
// DEVICE FINGERPRINT
// ============================================
function getDeviceFingerprint() {
    try {
        const scr = `${window.screen.width}x${window.screen.height}x${window.screen.colorDepth}`;
        const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
        const language = navigator.language;
        const userAgent = navigator.userAgent.substring(0, 100);
        return `${scr}|${timezone}|${language}|${userAgent}`;
    } catch (e) {
        return 'unknown';
    }
}

function showMathCaptcha(callback) {
    const captcha = generateMathCaptcha();
    const userAnswer = prompt(`🧮 Verify You're Human\n\nSolve this simple math question:\n\n${captcha.question}\n\nEnter your answer:`);
    if (userAnswer === null) { callback(false, null, null); return; }
    const parsed = parseInt(userAnswer);
    if (!isNaN(parsed) && parsed === captcha.answer) {
        callback(true, captcha.answer, captcha.question);
    } else {
        tg.showPopup({ title: '❌ Wrong Answer', message: 'Incorrect. Please try again.', buttons: [{type: 'ok'}] });
        callback(false, null, null);
    }
}

// ============================================
// SAFE POPUP
// ============================================
function safePopup(options) {
    try {
        if (typeof tg !== 'undefined' && tg.showPopup) tg.showPopup(options);
        else alert(typeof options === 'string' ? options : options.title + '\n\n' + options.message);
    } catch (e) { alert('An error occurred. Please try again.'); }
}

function safePopupWithCallback(options, callback) {
    try {
        if (typeof tg !== 'undefined' && tg.showPopup) tg.showPopup(options, callback);
        else {
            const message = options.title + '\n\n' + options.message;
            if (confirm(message)) { if (callback) callback('confirm'); }
            else { if (callback) callback('cancel'); }
        }
    } catch (e) {
        alert('An error occurred. Please try again.');
        if (callback) callback('cancel');
    }
}

function showInterstitialIfNeeded() {
    if (window._isBanned) return;
    if (interstitialAdsDisabled) return;
    var now = Date.now();
    if (now - lastAdTime < AD_COOLDOWN) return;
    lastAdTime = now;
    if (window.showInterstitialAd && typeof window.showInterstitialAd === 'function') {
        setTimeout(function() { window.showInterstitialAd().catch(() => {}); }, 500);
    }
}

// ============================================
// PAGE NAVIGATION
// ============================================
document.addEventListener('DOMContentLoaded', function() {
    try {
        tg.ready();
        tg.expand();
        function initializeApp() {
            if (tgUser) {
                loadUserData();
                loadSavedWallet();
                setupEventListeners();
                startCountdownTimer();
                loadAdStats();
                loadActiveReferrals();
                loadTasks();
                loadReferralProgress();
            } else { setTimeout(initializeApp, 100); }
        }
        initializeApp();
    } catch (e) { console.log('Error initializing app'); }
    document.addEventListener('click', function(e) {
        if (window._isBanned) return;
        var target = e.target.closest('button');
        if (!target) return;
        if (target.classList.contains('back-btn') || target.classList.contains('no-ad') || target.id === 'watchAdBtn' || target.classList.contains('currency-btn')) return;
        if (target.type === 'submit' && target.closest('#withdrawForm')) return;
        showInterstitialIfNeeded();
    });
});

function navigateTo(page) {
    if (window._isBanned) return;
    const pages = {'dashboard':'dashboard.html','deposit':'deposit.html','withdraw':'withdraw.html','history':'history.html','index':'index.html'};
    if (pages[page]) { showInterstitialIfNeeded(); window.location.href = pages[page]; }
}

function goBack() { window.history.back(); }

// ============================================
// CURRENCY SELECTION
// ============================================
function selectCurrency(currency) {
    window.selectedCurrency = currency;
    var usdtBtn = document.getElementById('usdtBtn'), gramBtn = document.getElementById('gramBtn');
    var usdtGroup = document.getElementById('usdtAddressGroup'), gramGroup = document.getElementById('gramAddressGroup');
    var networkLabel = document.getElementById('networkLabel');
    if (currency === 'usdt') {
        if (usdtBtn) usdtBtn.classList.add('active');
        if (gramBtn) gramBtn.classList.remove('active');
        if (usdtGroup) usdtGroup.style.display = 'block';
        if (gramGroup) gramGroup.style.display = 'none';
        if (networkLabel) networkLabel.textContent = 'Polygon';
    } else {
        if (gramBtn) gramBtn.classList.add('active');
        if (usdtBtn) usdtBtn.classList.remove('active');
        if (gramGroup) gramGroup.style.display = 'block';
        if (usdtGroup) usdtGroup.style.display = 'none';
        if (networkLabel) networkLabel.textContent = 'TON';
    }
    var feeNetEl = document.getElementById('feeNet');
    if (feeNetEl) {
        var currentText = feeNetEl.textContent.replace('~', '').replace(' in GRAM', '');
        feeNetEl.textContent = currency === 'gram' ? '~' + currentText + ' in GRAM' : currentText;
    }
}

// ============================================
// USER DATA
// ============================================
async function loadUserData(retries = 3) {
    if (window._isBanned) return;
    if (isLoading) return;
    isLoading = true;
    try {
        const userId = tgUser ? tgUser.id : '0';
        const response = await fetch(`${API_BASE}/api/user?telegram_id=${userId}`);
        if (response.status === 403) {
            let bannedData = null;
            try { bannedData = await response.json(); } catch (e) {}
            const msg = (bannedData && bannedData.message) ? bannedData.message : '';
            if (msg.toLowerCase().includes('suspended') || msg.toLowerCase().includes('banned')) {
                isLoading = false;
                showBanScreen(msg);
                return;
            }
        }
        const data = await response.json();
        if (data.success) {
            interstitialAdsDisabled = data.interstitial_ads_disabled || false;
            isDataLoaded = true;
            updateUI(data);
            updateFields(data);
            updateReferral(data);
            updateDashboardUI(data);
            updateDailyEarnings(data);
            await updateReferralStats(userId);
            await updateWelcomeBonusButton(data);
            updateTierButtons(data);
            updateClaimReferralButton(data);
            var loadingEl = document.getElementById('loadingMessage');
            var appContent = document.getElementById('appContent');
            if (loadingEl) loadingEl.style.display = 'none';
            if (appContent) appContent.style.display = 'block';
            if (data.interstitial_ads_disabled) {
                const disableBtn = document.getElementById('disableAdsBtn');
                if (disableBtn) { disableBtn.textContent = '✅ Ads Disabled'; disableBtn.disabled = true; disableBtn.style.opacity = '0.5'; }
            }
            loadAdStats();
            loadReferralProgress();
        }
    } catch (error) {
        if (retries > 0 && !window._isBanned) setTimeout(() => loadUserData(retries - 1), 1000);
    } finally { isLoading = false; }
}

function refreshData() {
    if (window._isBanned) return;
    showInterstitialIfNeeded();
    var balanceEl = document.getElementById('balance');
    var totalEarningsEl = document.getElementById('totalEarnings');
    if (balanceEl) balanceEl.textContent = '⏳ ...';
    if (totalEarningsEl) totalEarningsEl.textContent = '⏳ ...';
    setTimeout(function() {
        loadUserData(); loadSavedWallet(); loadAdStats();
        loadActiveReferrals(); loadTasks(); loadReferralProgress();
    }, 300);
}

async function updateReferralStats(userId) {
    if (window._isBanned) return;
    try {
        const response = await fetch(`${API_BASE}/api/referral_stats/${userId}`);
        const data = await response.json();
        if (data.success) {
            var rc = document.getElementById('referralCount');
            var re = document.getElementById('referralEarned');
            var lc = document.getElementById('level1Count');
            var le = document.getElementById('level1Earnings');
            if (rc) rc.textContent = data.total_referrals || 0;
            if (re) re.textContent = '$' + Number(data.total_earnings || 0).toFixed(3);
            if (lc) lc.textContent = data.level1_count || 0;
            if (le) le.textContent = '$' + Number(data.level1_earnings || 0).toFixed(3);
        }
    } catch (error) {}
}

function updateUI(data) {
    var b = document.getElementById('balance'); if (b) b.textContent = '$' + Number(data.balance || 0).toFixed(3);
    var te = document.getElementById('totalEarnings'); if (te) te.textContent = '$' + Number(data.total_earnings || 0).toFixed(3);
    var ie = document.getElementById('investmentEarnings'); if (ie) ie.textContent = '$' + Number(data.investment_earnings || 0).toFixed(3);
    var rd = document.getElementById('referralEarningsDisplay'); if (rd) rd.textContent = '$' + Number(data.referral_earned || 0).toFixed(3);
    var ad = document.getElementById('adEarningsDisplay'); if (ad) ad.textContent = '$' + Number(data.total_ad_earnings || 0).toFixed(3);
    var tsk = document.getElementById('tasksEarningsDisplay'); if (tsk) tsk.textContent = '$' + Number(data.tasks_earnings || 0).toFixed(3);
}

function updateDashboardUI(data) {
    var ids = {'dashBalance':'balance','dashInvested':'total_invested','dashEarned':'total_earnings','dashDeposited':'total_deposited','dashAdEarnings':'total_ad_earnings','dashTasksEarnings':'tasks_earnings'};
    for (var id in ids) {
        var el = document.getElementById(id);
        if (el) el.textContent = '$' + Number(data[ids[id]] || 0).toFixed(3);
    }
    var dr = document.getElementById('dashReferrals');
    if (dr) dr.textContent = data.referrals || 0;
}

function updateDailyEarnings(data) {
    var dailyEl = document.getElementById('dailyEarnings');
    if (dailyEl) dailyEl.textContent = '+$' + Number(data.expected_daily_earnings || 0).toFixed(2) + ' / day';
}

function updateWelcomeBonusButton(data) {
    const btn = document.getElementById('claimWelcomeBtn');
    if (!btn) return;
    if (data.has_received_welcome_bonus) {
        btn.textContent = '✅ Welcome';
        btn.disabled = true;
        btn.style.opacity = '0.5';
        btn.style.cursor = 'default';
        btn.style.background = 'rgba(0,255,135,0.1)';
        btn.style.color = '#00ff87';
    } else {
        btn.textContent = '🎁 Welcome';
        btn.disabled = false;
        btn.style.opacity = '1';
        btn.style.cursor = 'pointer';
        btn.style.background = 'linear-gradient(135deg,#ffd93d,#f9a825)';
        btn.style.color = '#0a0e17';
    }
}

function updateClaimReferralButton(data) {
    var btn = document.getElementById('claimReferralEarningsBtn');
    if (!btn) return;
    var pending = Number(data.pending_referral_rewards || 0);
    if (pending > 0) {
        btn.textContent = '💰 Available Earnings: $' + pending.toFixed(3) + ' (Claim)';
        btn.disabled = false;
        btn.style.background = 'linear-gradient(135deg,#00ff87,#00cc6a)';
        btn.style.color = '#0a0e17';
        btn.style.cursor = 'pointer';
        btn.style.opacity = '1';
    } else {
        btn.textContent = '💰 Available Earnings: $0.000';
        btn.disabled = true;
        btn.style.background = '#495670';
        btn.style.color = '#ccd6f0';
        btn.style.cursor = 'not-allowed';
        btn.style.opacity = '0.6';
    }
}

function updateTierButtons(data) {
    const userTier = data.referral_tier || 'free';
    const tierOrder = ['free', 'bronze', 'silver', 'gold', 'diamond'];
    document.querySelectorAll('.tier-card').forEach(card => {
        const btn = card.querySelector('.tier-btn');
        if (!btn) return;
        const nameEl = card.querySelector('.tier-name');
        if (!nameEl) return;
        const tierName = nameEl.textContent.toLowerCase();
        if (tierName === userTier) {
            btn.textContent = 'Current';
            btn.disabled = true;
            btn.className = 'tier-btn current';
            btn.style.background = '#495670';
            btn.style.color = 'white';
            btn.style.cursor = 'default';
            btn.onclick = null;
        } else {
            const userIndex = tierOrder.indexOf(userTier);
            const cardIndex = tierOrder.indexOf(tierName);
            if (cardIndex > userIndex) {
                btn.textContent = 'Upgrade';
                btn.disabled = false;
                btn.className = 'tier-btn';
                btn.style.background = '';
                btn.style.color = '';
                btn.style.cursor = 'pointer';
            } else {
                btn.textContent = 'Locked';
                btn.disabled = true;
                btn.className = 'tier-btn locked';
                btn.style.background = '#2a2a2a';
                btn.style.color = '#555';
                btn.style.cursor = 'default';
                btn.onclick = null;
            }
        }
    });
}

function updateFields(data) {
    var fields = data.fields || [];
    window.fieldData = {};
    for (var i = 1; i <= 3; i++) {
        var statusEl = document.getElementById('field' + i + 'Status');
        var amountEl = document.getElementById('field' + i + 'Amount');
        var daysEl = document.getElementById('field' + i + 'Days');
        var earnedEl = document.getElementById('field' + i + 'Earned');
        var progressEl = document.getElementById('field' + i + 'Progress');
        var cardEl = document.getElementById('field' + i);
        var btnEl = document.getElementById('field' + i + 'Btn');
        var timerEl = document.getElementById('field' + i + 'Timer');
        if (!statusEl || !amountEl || !daysEl || !earnedEl || !progressEl || !cardEl || !btnEl || !timerEl) continue;
        var field = fields.find(function(f) { return f.field_number === i; });
        if (field) {
            var lockPeriod = field.lock_period || 30;
            var isLocked = field.is_locked || false;
            var unlockDate = new Date(field.unlock_date);
            var now = new Date();
            var daysRemaining = Math.max(0, Math.ceil((unlockDate - now) / (1000 * 60 * 60 * 24)));
            var daysElapsed = lockPeriod - daysRemaining;
            window.fieldData[i] = { unlock_date: field.unlock_date, is_locked: isLocked, lock_period: lockPeriod, is_ready: false };
            amountEl.textContent = '$' + field.amount.toFixed(3);
            daysEl.textContent = isLocked ? daysElapsed + '/' + lockPeriod + ' days' : lockPeriod + '/' + lockPeriod + ' days';
            var displayEarned = isLocked ? field.expected_return || 0 : field.paid_out || 0;
            earnedEl.textContent = '$' + displayEarned.toFixed(3);
            var progress = isLocked ? ((lockPeriod - daysRemaining) / lockPeriod) * 100 : 100;
            progressEl.style.width = Math.min(progress, 100) + '%';
            cardEl.className = 'field-card active';
            btnEl.textContent = '🔒 Locked';
            btnEl.disabled = true;
            btnEl.style.opacity = '0.5';
            btnEl.style.cursor = 'not-allowed';
            btnEl.onclick = null;
        } else {
            statusEl.textContent = '✅ Available';
            statusEl.className = 'field-status available';
            statusEl.style.color = '#8247E5';
            amountEl.textContent = '$0.000';
            daysEl.textContent = '0 days';
            earnedEl.textContent = '$0.000';
            progressEl.style.width = '0%';
            cardEl.className = 'field-card';
            btnEl.textContent = '🌱 Plant Now';
            btnEl.disabled = false;
            btnEl.style.opacity = '1';
            btnEl.style.cursor = 'pointer';
            btnEl.onclick = (function(fn) { return function() { showInterstitialIfNeeded(); investField(fn); }; })(i);
            window.fieldData[i] = null;
        }
    }
}

let claimInProgress = false;

async function claimInvestment(fieldNumber) {
    if (window._isBanned) return;
    if (claimInProgress) return;
    claimInProgress = true;
    const userId = tgUser ? tgUser.id : '0';
    if (!userId || userId === '0') {
        safePopup({ title: '❌ Error', message: 'User not authenticated.', buttons: [{type: 'ok'}] });
        claimInProgress = false;
        return;
    }
    const btn = document.getElementById('field' + fieldNumber + 'Btn');
    const originalText = btn ? btn.textContent : '';
    if (btn) { btn.textContent = '⏳ Processing...'; btn.disabled = true; btn.style.opacity = '0.7'; }
    safePopupWithCallback({
        title: '🌾 Claim Investment',
        message: 'Are you sure you want to claim Field #' + fieldNumber + '?',
        buttons: [{id:'cancel',type:'cancel'},{id:'confirm',type:'ok',text:'✅ Claim'}]
    }, async function(buttonId) {
        if (buttonId === 'confirm') {
            try {
                const response = await fetch(`${API_BASE}/api/claim_investment`, {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ telegram_id: userId, field_number: fieldNumber })
                });
                const data = await response.json();
                if (data.success) {
                    safePopup({ title: '✅ Claimed!', message: 'You claimed $' + data.amount.toFixed(2) + ' USDT from Field #' + fieldNumber + '!', buttons: [{type: 'ok'}] });
                    setTimeout(function() {
                        loadUserData(); loadAdStats(); loadActiveReferrals(); loadTasks(); loadReferralProgress();
                        claimInProgress = false;
                        if (btn) { btn.textContent = originalText; btn.disabled = false; btn.style.opacity = '1'; }
                    }, 3000);
                } else {
                    safePopup({ title: '❌ Error', message: data.message || 'Failed to claim.', buttons: [{type: 'ok'}] });
                    claimInProgress = false;
                    if (btn) { btn.textContent = originalText; btn.disabled = false; btn.style.opacity = '1'; }
                }
            } catch (error) {
                safePopup({ title: '❌ Error', message: 'Network error. Please try again.', buttons: [{type: 'ok'}] });
                claimInProgress = false;
                if (btn) { btn.textContent = originalText; btn.disabled = false; btn.style.opacity = '1'; }
            }
        } else {
            claimInProgress = false;
            if (btn) { btn.textContent = originalText; btn.disabled = false; btn.style.opacity = '1'; }
        }
    });
}

function updateFieldTimers() {
    if (window._isBanned) return;
    if (document.getElementById('historyList')) return;
    var now = new Date();
    var utcNow = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate(), now.getUTCHours(), now.getUTCMinutes(), now.getUTCSeconds());
    for (var i = 1; i <= 3; i++) {
        var timerEl = document.getElementById('field' + i + 'Timer');
        var statusEl = document.getElementById('field' + i + 'Status');
        var btnEl = document.getElementById('field' + i + 'Btn');
        if (!timerEl || !statusEl || !btnEl) continue;
        var fieldData = window.fieldData ? window.fieldData[i] : null;
        if (!fieldData || !fieldData.unlock_date) { timerEl.textContent = '⏳ Payout: --:--:-- UTC'; timerEl.className = 'field-timer'; continue; }
        var isLocked = fieldData.is_locked === true;
        var lockPeriod = fieldData.lock_period || 30;
        var unlockDateStr = fieldData.unlock_date;
        if (unlockDateStr.endsWith('Z')) unlockDateStr = unlockDateStr.slice(0, -1);
        var unlockDate = new Date(unlockDateStr + 'Z').getTime();
        var timeLeft = unlockDate - utcNow;
        var isReady = (isLocked === true) && (timeLeft <= 0);
        fieldData.is_ready = isReady;
        if (isReady) {
            timerEl.textContent = '🟢 READY TO CLAIM!';
            timerEl.className = 'field-timer ready';
            timerEl.style.color = '#ffd93d';
            timerEl.style.animation = 'pulse-gold 1.5s infinite';
            btnEl.textContent = '🌾 Claim Now!';
            btnEl.disabled = false;
            btnEl.style.opacity = '1';
            btnEl.style.cursor = 'pointer';
            btnEl.style.background = 'linear-gradient(135deg, #ffd93d, #f9a825)';
            btnEl.style.color = '#0a0e17';
            btnEl.onclick = (function(fn) { return function() { claimInvestment(fn); }; })(i);
            statusEl.textContent = '✅ Ready to Claim!';
            statusEl.className = 'field-status ready';
            statusEl.style.color = '#ffd93d';
        } else if (isLocked === true && timeLeft > 0) {
            var days = Math.floor(timeLeft / (1000 * 60 * 60 * 24));
            var hours = Math.floor((timeLeft % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
            var minutes = Math.floor((timeLeft % (1000 * 60 * 60)) / (1000 * 60));
            var seconds = Math.floor((timeLeft % (1000 * 60)) / 1000);
            var timeString = days > 0 ? days + 'd ' + String(hours).padStart(2,'0') + ':' + String(minutes).padStart(2,'0') + ':' + String(seconds).padStart(2,'0') : String(hours).padStart(2,'0') + ':' + String(minutes).padStart(2,'0') + ':' + String(seconds).padStart(2,'0');
            timerEl.textContent = '🔄 Unlock in: ' + timeString + ' UTC';
            timerEl.className = 'field-timer countdown';
            btnEl.textContent = '🔒 Locked';
            btnEl.disabled = true;
            btnEl.style.opacity = '0.5';
            btnEl.style.cursor = 'not-allowed';
            btnEl.onclick = null;
            statusEl.textContent = '🔒 Locked';
            statusEl.className = 'field-status locked';
            statusEl.style.color = '#ff6b6b';
        } else if (isLocked === false) {
            timerEl.textContent = '🟢 Available (UTC)';
            timerEl.className = 'field-timer';
            btnEl.textContent = '🌱 Plant Now';
            btnEl.disabled = false;
            btnEl.style.opacity = '1';
            btnEl.style.cursor = 'pointer';
            btnEl.onclick = (function(fn) { return function() { showInterstitialIfNeeded(); investField(fn); }; })(i);
            statusEl.textContent = '✅ Available';
            statusEl.className = 'field-status available';
            statusEl.style.color = '#8247E5';
        }
    }
}

var style = document.createElement('style');
style.textContent = `@keyframes pulse-gold { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }`;
document.head.appendChild(style);

function startCountdownTimer() { updateFieldTimers(); if (timerInterval) clearInterval(timerInterval); timerInterval = setInterval(updateFieldTimers, 1000); }
function stopCountdownTimer() { if (timerInterval) { clearInterval(timerInterval); timerInterval = null; } }

async function updateReferral(data) {
    if (window._isBanned) return;
    var referralLink = document.getElementById('referralLinkText');
    var walletText = document.getElementById('walletText');
    var isConnected = walletText ? walletText.textContent.includes('Connected') : false;
    if (!referralLink) return;
    if (isConnected) {
        var userId = tgUser ? tgUser.id : '0';
        try {
            var response = await fetch(API_BASE + '/api/get_referral_code?telegram_id=' + userId + '&t=' + Date.now());
            var result = await response.json();
            if (result.success && result.referral_code) {
                referralLink.textContent = 'https://t.me/PlantUSDT_bot?start=' + result.referral_code;
                referralLink.style.color = '#ccd6f0';
            } else { referralLink.textContent = 'Error loading referral link'; referralLink.style.color = '#ff6b6b'; }
        } catch (error) { referralLink.textContent = 'Error loading referral link'; referralLink.style.color = '#ff6b6b'; }
    } else { referralLink.textContent = '⚠️ Save wallet to get referral link'; referralLink.style.color = '#ff6b6b'; }
}

async function copyReferral() {
    if (window._isBanned) return;
    showInterstitialIfNeeded();
    var userId = tgUser ? tgUser.id : '0';
    var referralLinkEl = document.getElementById('referralLinkText');
    try {
        var response = await fetch(API_BASE + '/api/get_referral_code?telegram_id=' + userId + '&t=' + Date.now());
        var data = await response.json();
        if (data.success && data.referral_code) {
            var referralLink = 'https://t.me/PlantUSDT_bot?start=' + data.referral_code;
            if (referralLinkEl) { referralLinkEl.textContent = referralLink; referralLinkEl.style.color = '#ccd6f0'; }
            var copied = false;
            try { await navigator.clipboard.writeText(referralLink); copied = true; } catch (e) {}
            if (!copied) {
                var textArea = document.createElement('textarea');
                textArea.value = referralLink;
                textArea.style.position = 'fixed'; textArea.style.left = '-9999px';
                document.body.appendChild(textArea);
                textArea.focus(); textArea.select();
                try { if (document.execCommand('copy')) copied = true; } catch (e) {}
                document.body.removeChild(textArea);
            }
            if (!copied) {
                safePopup({ title: '📋 Copy Referral Link', message: 'Copy manually:\n\n' + referralLink, buttons: [{type:'ok'}] });
                return;
            }
            safePopup({ title: '✅ Copied!', message: 'Referral link copied! Share it with friends! 🎉', buttons: [{type: 'ok'}] });
        } else {
            safePopup({ title: '❌ Error', message: 'Could not get referral link.', buttons: [{type: 'ok'}] });
        }
    } catch (error) { safePopup({ title: '❌ Error', message: 'Network error.', buttons: [{type: 'ok'}] }); }
}

async function claimReferralRewards() {
    if (window._isBanned) return;
    const userId = tgUser ? tgUser.id : '0';
    safePopupWithCallback({
        title: '💰 Claim Referral Rewards',
        message: 'Claim all available referral earnings to your balance?',
        buttons: [{id: 'cancel', type: 'cancel'}, {id: 'confirm', type: 'ok', text: '✅ Claim'}]
    }, async function(buttonId) {
        if (buttonId === 'confirm') {
            try {
                const response = await fetch(`${API_BASE}/api/claim_referral_rewards`, {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ telegram_id: userId })
                });
                const data = await response.json();
                if (data.success) {
                    safePopup({ title: '🎉 Claimed!', message: data.message + '\n\nNew balance: $' + data.new_balance.toFixed(3), buttons: [{type: 'ok'}] });
                    loadUserData();
                } else {
                    safePopup({ title: '❌ Error', message: data.message || 'Failed to claim.', buttons: [{type: 'ok'}] });
                }
            } catch (error) {
                safePopup({ title: '❌ Error', message: 'Network error.', buttons: [{type: 'ok'}] });
            }
        }
    });
}

async function saveWallet() {
    if (window._isBanned) return;
    showInterstitialIfNeeded();
    var userId = tgUser ? tgUser.id : '0';
    var walletInput = document.getElementById('walletInput');
    var walletAddress = walletInput ? walletInput.value.trim() : '';
    if (!walletAddress) { safePopup({title:'❌ Error', message:'Please enter a Polygon wallet address.', buttons:[{type:'ok'}]}); return; }
    if (!walletAddress.startsWith('0x') || walletAddress.length !== 42) { safePopup({title:'❌ Invalid Address', message:'Please enter a valid Polygon wallet address.', buttons:[{type:'ok'}]}); return; }
    if (walletAddress.toLowerCase() === PROJECT_WALLET.toLowerCase()) { safePopup({title:'❌ Invalid Wallet', message:'This is the project wallet.', buttons:[{type:'ok'}]}); return; }
    try {
        var response = await fetch(API_BASE + '/api/save_wallet', {
            method:'POST', headers:{'Content-Type':'application/json'},
            body:JSON.stringify({telegram_id:userId, wallet_address:walletAddress})
        });
        var data = await response.json();
        if (data.success) {
            safePopup({title:'✅ Wallet Saved!', message:'Wallet saved: ' + walletAddress.slice(0,6) + '...' + walletAddress.slice(-4), buttons:[{type:'ok'}]});
            updateWalletUI(walletAddress);
            loadUserData();
        } else { safePopup({title:'❌ Error', message:data.message || 'Failed to save wallet.', buttons:[{type:'ok'}]}); }
    } catch (error) { safePopup({title:'❌ Error', message:'Failed to save wallet.', buttons:[{type:'ok'}]}); }
}

function updateWalletUI(address) {
    var statusText = document.getElementById('walletText');
    var addressDisplay = document.getElementById('walletAddressDisplay');
    var walletInput = document.getElementById('walletInput');
    var saveBtn = document.getElementById('saveWalletBtn');
    var disconnectBtn = document.getElementById('disconnectWalletBtn');
    if (statusText) { statusText.textContent = '✅ Polygon Wallet Connected'; statusText.className = 'connected'; }
    if (addressDisplay) { addressDisplay.textContent = '📍 ' + address + ' (Polygon)'; addressDisplay.style.display = 'block'; }
    if (walletInput) { walletInput.value = address; walletInput.disabled = true; walletInput.style.opacity = '0.6'; }
    if (saveBtn) saveBtn.style.display = 'none';
    if (disconnectBtn) disconnectBtn.style.display = 'flex';
    loadUserData();
    setTimeout(function() {
        var userId = tgUser ? tgUser.id : '0';
        fetch(API_BASE + '/api/user?telegram_id=' + userId).then(r => r.json()).then(data => updateReferral(data));
    }, 500);
}

function resetWalletUI() {
    var statusText = document.getElementById('walletText');
    var addressDisplay = document.getElementById('walletAddressDisplay');
    var walletInput = document.getElementById('walletInput');
    var saveBtn = document.getElementById('saveWalletBtn');
    var disconnectBtn = document.getElementById('disconnectWalletBtn');
    if (statusText) { statusText.textContent = 'Polygon wallet not connected'; statusText.className = 'disconnected'; }
    if (addressDisplay) addressDisplay.style.display = 'none';
    if (walletInput) { walletInput.value = ''; walletInput.disabled = false; walletInput.style.opacity = '1'; }
    if (saveBtn) saveBtn.style.display = 'flex';
    if (disconnectBtn) disconnectBtn.style.display = 'none';
    loadUserData();
}

async function disconnectWallet() {
    if (window._isBanned) return;
    showInterstitialIfNeeded();
    var userId = tgUser ? tgUser.id : '0';
    safePopupWithCallback({
        title:'🔓 Disconnect Wallet',
        message:'Are you sure you want to disconnect your Polygon wallet?',
        buttons:[{id:'cancel',type:'cancel'},{id:'confirm',type:'ok',text:'Disconnect'}]
    }, async function(buttonId) {
        if (buttonId === 'confirm') {
            try {
                var response = await fetch(API_BASE + '/api/save_wallet', {
                    method:'POST', headers:{'Content-Type':'application/json'},
                    body:JSON.stringify({telegram_id:userId, wallet_address:''})
                });
                var data = await response.json();
                if (data.success) { resetWalletUI(); safePopup({title:'✅ Disconnected', message:'Polygon wallet disconnected.', buttons:[{type:'ok'}]}); }
                else { safePopup({title:'❌ Error', message:'Failed to disconnect.', buttons:[{type:'ok'}]}); }
            } catch (error) { safePopup({title:'❌ Error', message:'Failed to disconnect.', buttons:[{type:'ok'}]}); }
        }
    });
}

async function loadSavedWallet() {
    if (window._isBanned) return;
    var userId = tgUser ? tgUser.id : '0';
    try {
        var response = await fetch(API_BASE + '/api/get_wallet?telegram_id=' + userId);
        var data = await response.json();
        if (data.success && data.wallet_address) updateWalletUI(data.wallet_address);
    } catch (error) {}
}

async function setWallet() {
    if (window._isBanned) return;
    showInterstitialIfNeeded();
    var userId = tgUser ? tgUser.id : '0';
    try {
        var response = await fetch(API_BASE + '/api/get_wallet?telegram_id=' + userId);
        var data = await response.json();
        if (data.success && data.wallet_address) {
            var withdrawAddress = document.getElementById('withdrawAddress');
            if (withdrawAddress) {
                withdrawAddress.value = data.wallet_address;
                safePopup({title:'✅ Wallet Loaded!', message:'Wallet loaded.', buttons:[{type:'ok'}]});
            }
        } else {
            safePopup({ title: '❌ No Wallet Found', message: 'Please save a wallet first.', buttons: [{type: 'ok'}] });
        }
    } catch (error) { safePopup({ title: '❌ Error', message: 'Failed to load wallet.', buttons: [{type: 'ok'}] }); }
}

function calculateReturn(amount, days) {
    const multipliers = {1: 1.02, 7: 1.18, 30: 1.80};
    return amount * (multipliers[days] || 1.80);
}

function getLockOptions() {
    return [{days:1,returnPercent:2},{days:7,returnPercent:18},{days:30,returnPercent:80}];
}

async function investFieldWithLock(fieldNumber) {
    if (window._isBanned) return;
    showInterstitialIfNeeded();
    const userId = tgUser ? tgUser.id : '0';
    const amount = prompt('Enter amount to invest in Field #' + fieldNumber + ' (min $5.00, max $100.00):');
    if (!amount) return;
    const amountNum = parseFloat(amount.replace('$', '').trim());
    if (isNaN(amountNum) || amountNum < 5 || amountNum > 100) {
        safePopup({title:'❌ Invalid Amount', message:'Please enter between $5.00 and $100.00.', buttons:[{type:'ok'}]});
        return;
    }
    const options = getLockOptions();
    let message = '📊 Choose lock period:\n\n';
    options.forEach(opt => {
        const returnAmount = calculateReturn(amountNum, opt.days);
        const profit = returnAmount - amountNum;
        message += '• ' + opt.days + ' day' + (opt.days > 1 ? 's' : '') + ': +' + opt.returnPercent + '% → $' + returnAmount.toFixed(2) + ' (+$' + profit.toFixed(2) + ')\n';
    });
    message += '\n\nEnter 1, 7, or 30:';
    const lockPeriod = prompt(message);
    if (!lockPeriod) return;
    const days = parseInt(lockPeriod);
    if (![1, 7, 30].includes(days)) {
        safePopup({title:'❌ Invalid Option', message:'Please enter 1, 7, or 30.', buttons:[{type:'ok'}]});
        return;
    }
    const expectedReturn = calculateReturn(amountNum, days);
    const profit = expectedReturn - amountNum;
    safePopupWithCallback({
        title: '📊 Confirm Investment',
        message: 'Field #' + fieldNumber + '\n\n💰 Amount: $' + amountNum.toFixed(2) + '\n⏱️ Lock: ' + days + ' days\n📈 Return: $' + expectedReturn.toFixed(2) + '\n✅ Profit: +$' + profit.toFixed(2),
        buttons: [{id:'cancel',type:'cancel'},{id:'confirm',type:'ok',text:'✅ Confirm'}]
    }, async function(buttonId) {
        if (buttonId === 'confirm') {
            try {
                const response = await fetch(API_BASE + '/api/invest_locked', {
                    method:'POST', headers:{'Content-Type':'application/json'},
                    body:JSON.stringify({ telegram_id: userId, field_number: fieldNumber, amount: amountNum, lock_period: days })
                });
                if (!response.ok) { safePopup({ title:'❌ Error', message:'Something went wrong.', buttons:[{type:'ok'}] }); return; }
                const data = await response.json();
                if (data.success) {
                    safePopup({
                        title:'✅ Success!',
                        message:'Invested $' + amountNum.toFixed(2) + ' in Field #' + fieldNumber + '!\n🔒 Locked for ' + days + ' days.\n📈 Expected return: $' + expectedReturn.toFixed(2),
                        buttons:[{type:'ok'}]
                    });
                    loadUserData();
                } else { safePopup({ title:'❌ Error', message:data.message || 'Investment failed.', buttons:[{type:'ok'}] }); }
            } catch (error) { safePopup({ title:'❌ Error', message:'Network error.', buttons:[{type:'ok'}] }); }
        }
    });
}

async function investField(fieldNumber) { await investFieldWithLock(fieldNumber); }

function copyAddress() {
    if (window._isBanned) return;
    showInterstitialIfNeeded();
    var addressElement = document.getElementById('addressText');
    var address = addressElement ? addressElement.textContent.trim() : '';
    if (!address) {
        var displayElement = document.querySelector('.address');
        if (displayElement) address = displayElement.textContent.trim();
    }
    address = address.replace(/\s+/g, '').trim();
    if (address && address.startsWith('0x') && address.length === 42) {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(address).then(function() {
                safePopup({ title: '✅ Copied!', message: 'Address copied.', buttons: [{type: 'ok'}] });
            }).catch(function() {
                var textArea = document.createElement('textarea');
                textArea.value = address; document.body.appendChild(textArea);
                textArea.select(); document.execCommand('copy');
                document.body.removeChild(textArea);
                safePopup({ title: '✅ Copied!', message: 'Address copied.', buttons: [{type: 'ok'}] });
            });
        } else {
            var textArea = document.createElement('textarea');
            textArea.value = address; document.body.appendChild(textArea);
            textArea.select(); document.execCommand('copy');
            document.body.removeChild(textArea);
            safePopup({ title: '✅ Copied!', message: 'Address copied.', buttons: [{type: 'ok'}] });
        }
    } else { safePopup({ title: '❌ Error', message: 'Invalid address.', buttons: [{type: 'ok'}] }); }
}

async function checkDeposit() {
    if (window._isBanned) return;
    var statusDiv = document.getElementById('depositStatus');
    if (statusDiv) {
        statusDiv.textContent = '🔍 Checking Polygon for deposits...';
        try {
            var userId = tgUser ? tgUser.id : '0';
            var response = await fetch(API_BASE + '/api/check_deposit?telegram_id=' + userId);
            var data = await response.json();
            if (data.success) { statusDiv.textContent = '✅ Deposit detected!'; loadUserData(); }
            else { statusDiv.textContent = '⏳ No new deposits found.'; }
        } catch (error) { statusDiv.textContent = '❌ Error checking deposits.'; }
    }
}

async function checkDepositWithAmount() {
    if (window._isBanned) return;
    showInterstitialIfNeeded();
    const userId = tgUser?.id || '0';
    const amountInput = document.getElementById('depositAmount');
    const amount = amountInput?.value;
    if (!amount || parseFloat(amount) < 5) {
        safePopup({ title: '⚠️ Invalid Amount', message: 'Please enter at least $5 USDT.', buttons: [{type: 'ok'}] });
        return;
    }
    const statusDiv = document.getElementById('depositStatus');
    if (statusDiv) {
        statusDiv.textContent = '🔍 Checking Polygon for deposits...';
        statusDiv.className = 'deposit-status pending';
        statusDiv.style.display = 'block';
        try {
            const response = await fetch(`${API_BASE}/api/check_deposit_with_amount?telegram_id=${userId}&expected_amount=${parseFloat(amount)}`);
            const data = await response.json();
            if (data.success) {
                statusDiv.textContent = '✅ ' + data.message;
                statusDiv.className = 'deposit-status success';
                setTimeout(() => { window.location.reload(); }, 2000);
            } else {
                statusDiv.textContent = '⏳ ' + data.message;
                statusDiv.className = 'deposit-status pending';
            }
        } catch (error) {
            statusDiv.textContent = '❌ Error checking deposits.';
            statusDiv.className = 'deposit-status error';
        }
    }
}

function filterHistory(type) {
    if (window._isBanned) return;
    var activeButton = null;
    var buttons = document.querySelectorAll('.filter-btn');
    for (var i = 0; i < buttons.length; i++) {
        var btnText = buttons[i].textContent.toLowerCase();
        if (btnText === type || btnText.includes(type)) { activeButton = buttons[i]; break; }
    }
    if (!activeButton && buttons.length > 0) activeButton = buttons[0];
    for (var i = 0; i < buttons.length; i++) buttons[i].classList.remove('active');
    if (activeButton) activeButton.classList.add('active');
    var historyList = document.getElementById('historyList');
    if (!historyList) return;
    historyList.textContent = 'Loading...';
    var userId = tgUser ? tgUser.id : '0';
    var url1 = API_BASE + '/api/real_history?telegram_id=' + userId;
    var url2 = API_BASE + '/api/investments/' + userId;
    Promise.all([fetch(url1), fetch(url2)])
        .then(function(responses) { return Promise.all(responses.map(function(r) { return r.json(); })); })
        .then(function(data) {
            var allTransactions = [];
            if (data[0].transactions && data[0].transactions.length > 0) allTransactions = allTransactions.concat(data[0].transactions);
            if (data[1].transactions && data[1].transactions.length > 0) {
                data[1].transactions.forEach(function(tx) { tx.type = 'investment'; });
                allTransactions = allTransactions.concat(data[1].transactions);
            }
            if (allTransactions.length === 0) { historyList.textContent = 'No transactions found.'; return; }
            if (type !== 'all') {
                allTransactions = allTransactions.filter(function(tx) {
                    if (type === 'deposits') return tx.type === 'deposit' || tx.type === 'deposits';
                    if (type === 'withdrawals') return tx.type === 'withdraw' || tx.type === 'withdrawal' || tx.type === 'withdrawals';
                    if (type === 'earnings') return tx.type === 'earnings' || tx.type === 'earning' || tx.type === 'payout' || tx.type === 'referral_earnings' || tx.type === 'ad_earnings' || tx.type === 'tasks_earnings';
                    if (type === 'investments') return tx.type === 'investment' || tx.type === 'investments';
                    return tx.type === type;
                });
            }
            if (allTransactions.length === 0) { historyList.textContent = 'No ' + type + ' transactions found.'; return; }
            allTransactions.sort(function(a, b) { return new Date(b.date) - new Date(a.date); });
            renderHistory(allTransactions);
        })
        .catch(function(error) { historyList.textContent = 'Error loading history.'; });
}

function renderHistory(transactions) {
    var historyList = document.getElementById('historyList');
    if (!historyList) return;
    var html = '';
    for (var i = 0; i < transactions.length; i++) {
        var tx = transactions[i];
        var icon = tx.type === 'deposit' ? '📥' : tx.type === 'withdraw' ? '📤' : tx.type === 'investment' ? '🌱' : tx.type === 'referral_earnings' ? '🎁' : tx.type === 'ad_earnings' ? '📺' : tx.type === 'tasks_earnings' ? '✅' : '💰';
        var status = tx.status || 'completed';
        var displayText = tx.type.charAt(0).toUpperCase() + tx.type.slice(1);
        if (tx.type === 'referral_earnings') displayText = 'Referral Bonus';
        if (tx.type === 'ad_earnings') displayText = 'Ad Earnings';
        if (tx.type === 'tasks_earnings') displayText = 'Tasks Earnings';
        var amountDisplay = '$' + tx.amount.toFixed(3);
        if (tx.type === 'investment' && tx.field) amountDisplay = '$' + tx.amount.toFixed(3) + ' (Field ' + tx.field + ')';
        var statusBadge = (tx.type === 'withdraw' && tx.status === 'pending') ? ' ⏳' : '';
        html += '<div class="history-item">' +
            '<div class="history-icon">' + icon + '</div>' +
            '<div class="history-details">' +
                '<div class="history-type">' + displayText + ' 🟣 Polygon' + statusBadge + '</div>' +
                '<div class="history-date">' + tx.date + '</div>' +
            '</div>' +
            '<div class="history-amount ' + status + '">' + amountDisplay + '</div>' +
        '</div>';
    }
    historyList.innerHTML = html;
}

function setupEventListeners() {
    var withdrawForm = document.getElementById('withdrawForm');
    if (withdrawForm) {
        withdrawForm.addEventListener('submit', function(e) {
            e.preventDefault();
            if (window._isBanned) return;
            var submitBtn = document.querySelector('.withdraw-btn');
            if (submitBtn && submitBtn.disabled) return;
            showInterstitialIfNeeded();
            var userId = tgUser ? tgUser.id : '0';
            var currency = window.selectedCurrency || 'usdt';
            var amountInput = document.getElementById('withdrawAmount');
            var addressInput = document.getElementById('withdrawAddress');
            var gramInput = document.getElementById('gramAddress');
            var amount = 0;
            if (window.withdrawAmount !== undefined && window.withdrawAmount > 0) amount = window.withdrawAmount;
            else if (amountInput && amountInput.value) amount = parseFloat(amountInput.value);
            else {
                var fullBalanceEl = document.getElementById('fullBalanceDisplay');
                if (fullBalanceEl) amount = parseFloat(fullBalanceEl.textContent.replace('$', ''));
            }
            var address = '';
            if (currency === 'usdt') {
                address = addressInput ? addressInput.value : '';
                if (!address || !address.startsWith('0x') || address.length !== 42) {
                    safePopup({title:'❌ Error', message:'Please enter a valid Polygon wallet address.', buttons:[{type:'ok'}]});
                    return;
                }
                if (address.toLowerCase() === PROJECT_WALLET.toLowerCase()) {
                    safePopup({title:'❌ Invalid Wallet', message:'Cannot withdraw to project wallet.', buttons:[{type:'ok'}]});
                    return;
                }
            } else {
                address = gramInput ? gramInput.value.trim() : '';
                if (!isValidTonAddress(address)) {
                    safePopup({title:'❌ Error', message:'Please enter a valid TON wallet address.', buttons:[{type:'ok'}]});
                    return;
                }
            }
            if (!amount || amount < 1) {
                safePopup({title:'❌ Error', message:'Please enter at least $1 USDT.', buttons:[{type:'ok'}]});
                return;
            }
            if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = '⏳ Processing...'; }
            fetch(API_BASE + '/api/withdraw', {
                method:'POST', headers:{'Content-Type':'application/json'},
                body:JSON.stringify({ telegram_id: userId, amount: parseFloat(amount), address: address, currency: currency })
            })
            .then(function(response) { return response.json(); })
            .then(function(data) {
                if (data.success) {
                    safePopup({title:'✅ Success!', message:data.message || 'Withdrawal submitted!', buttons:[{type:'ok'}]});
                    if (amountInput) amountInput.value = '';
                    if (addressInput) addressInput.value = '';
                    if (gramInput) gramInput.value = '';
                } else {
                    if (data.cooldown_remaining) safePopup({title:'⏳ Cooldown Active', message:data.message, buttons:[{type:'ok'}]});
                    else safePopup({title:'❌ Error', message:data.message || 'Withdrawal failed.', buttons:[{type:'ok'}]});
                }
            })
            .catch(function(error) {
                safePopup({title:'❌ Error', message:'Network error.', buttons:[{type:'ok'}]});
            })
            .finally(function() {
                setTimeout(function() {
                    if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = 'Withdraw Full Balance'; }
                }, 3000);
            });
        });
    }
}

async function canWatchAd() { return true; }

function updateAdUI(dailyCount) {
    window._latestAdCount = dailyCount;
    window._adCountTimestamp = Date.now();
    const adsTodayEl = document.getElementById('adsToday');
    if (adsTodayEl) adsTodayEl.textContent = String(dailyCount);
    const watchBtn = document.getElementById('watchAdBtn');
    if (watchBtn) { watchBtn.disabled = false; watchBtn.textContent = '▶️ Watch Ad — Support Giveaways'; }
    const statusEl = document.getElementById('adStatus');
    if (statusEl) statusEl.style.display = 'none';
}

async function watchRewardedAd() {
    if (window._isBanned) return false;
    if (!window.showRewardedAd) {
        safePopup({ title: '❌ Ad Not Available', message: 'No ads available right now.', buttons: [{type: 'ok'}] });
        return false;
    }
    try {
        const result = await window.showRewardedAd();
        if (result.done && !result.error && result.state === 'destroy') {
            const captcha = generateMathCaptcha();
            const userAnswer = prompt(`🧮 Verify You're Human\n\n${captcha.question}\n\nEnter your answer:`);
            if (userAnswer === null) return false;
            const parsed = parseInt(userAnswer);
            if (isNaN(parsed) || parsed !== captcha.answer) {
                safePopup({ title: '❌ Wrong Answer', message: 'Incorrect. Please try again.', buttons: [{type: 'ok'}] });
                return false;
            }
            const userId = tgUser ? tgUser.id : '0';
            const fingerprint = getDeviceFingerprint();
            try {
                const response = await fetch(API_BASE + '/api/credit_ad_reward', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ telegram_id: userId, captcha_answer: captcha.answer, captcha_question: captcha.question, device_fingerprint: fingerprint })
                });
                const data = await response.json();
                if (data.success) {
                    updateAdUI(data.daily_ad_count || 0);
                    safePopup({
                        title: '✅ Ad Watched!',
                        message: 'Thanks for supporting the community giveaway! 🎁\n\nYour ad helps fund the weekly prize pool. Winners announced every Friday.',
                        buttons: [{type: 'ok'}]
                    });
                    setTimeout(() => { loadUserData(); loadActiveReferrals(); loadTasks(); loadReferralProgress(); }, 2000);
                    return true;
                } else if (data.need_captcha) {
                    safePopup({ title: '🧮 Verification Required', message: data.message || 'Please solve the math question.', buttons: [{type: 'ok'}] });
                    return false;
                } else {
                    safePopup({ title: '❌ Error', message: data.message || 'Failed to process ad.', buttons: [{type: 'ok'}] });
                    return false;
                }
            } catch (error) {
                safePopup({ title: '❌ Error', message: 'Network error.', buttons: [{type: 'ok'}] });
                return false;
            }
        } else {
            safePopup({ title: '❌ Ad Not Available', message: 'No ads available right now.', buttons: [{type: 'ok'}] });
            return false;
        }
    } catch (error) {
        safePopup({ title: '❌ Error', message: 'Network error.', buttons: [{type: 'ok'}] });
        return false;
    }
}

async function loadAdStats() {
    if (window._isBanned) return;
    const userId = tgUser ? tgUser.id : '0';
    try {
        const response = await fetch(API_BASE + '/api/user?telegram_id=' + userId + '&t=' + Date.now());
        const userData = await response.json();
        if (!userData.success) return;
        const serverDailyCount = userData.daily_ad_count || 0;
        let finalCount = serverDailyCount;
        if (window._latestAdCount !== null && window._adCountTimestamp !== null) {
            const timeSinceUpdate = Date.now() - window._adCountTimestamp;
            if (timeSinceUpdate < 10000 && window._latestAdCount > serverDailyCount) finalCount = window._latestAdCount;
        }
        const adsTodayEl = document.getElementById('adsToday');
        if (adsTodayEl) adsTodayEl.textContent = String(finalCount);
        const watchBtn = document.getElementById('watchAdBtn');
        if (watchBtn) { watchBtn.disabled = false; watchBtn.textContent = '▶️ Watch Ad — Support Giveaways'; }
    } catch (error) {}
}

async function upgradeReferralTier(tier) {
    if (window._isBanned) return;
    showInterstitialIfNeeded();
    const userId = tgUser ? tgUser.id : '0';
    if (!userId || userId === '0') {
        safePopup({ title: '❌ Error', message: 'User not authenticated.', buttons: [{type: 'ok'}] });
        return;
    }
    safePopupWithCallback({
        title: '📊 Upgrade Referral Tier',
        message: 'Upgrade to ' + tier.toUpperCase() + ' tier?\n\nPERMANENT upgrade. No refunds.',
        buttons: [{id:'cancel',type:'cancel'},{id:'confirm',type:'ok',text:'✅ Upgrade'}]
    }, async function(buttonId) {
        if (buttonId === 'confirm') {
            try {
                const response = await fetch(API_BASE + '/api/upgrade_tier', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ telegram_id: userId, tier: tier })
                });
                const data = await response.json();
                if (data.success) {
                    safePopup({ title: '✅ Upgrade Successful!', message: data.message + '\n\nNew balance: $' + data.new_balance.toFixed(2), buttons: [{type: 'ok'}] });
                    setTimeout(function() { loadUserData(); }, 1000);
                } else {
                    safePopup({ title: '❌ Error', message: data.message || 'Upgrade failed.', buttons: [{type: 'ok'}] });
                }
            } catch (error) {
                safePopup({ title: '❌ Error', message: 'Network error.', buttons: [{type: 'ok'}] });
            }
        }
    });
}

async function loadActiveReferrals() {
    if (window._isBanned) return;
    const userId = tgUser ? tgUser.id : '0';
    try {
        const response = await fetch(`${API_BASE}/api/get_active_referrals/${userId}`);
        const data = await response.json();
        if (data.success) {
            const activeRefsEl = document.getElementById('activeReferralsCount');
            if (activeRefsEl) activeRefsEl.textContent = data.active_count + ' / ' + data.total_referrals;
            const listEl = document.getElementById('activeReferralList');
            if (listEl) {
                if (data.active_list && data.active_list.length > 0) {
                    const total = data.active_list.length;
                    const showCount = 3;
                    const hasMore = total > showCount;
                    const visibleRefs = data.active_list.slice(0, showCount);
                    let html = `<div style="font-size:12px;color:#8892b0;margin-bottom:6px;">👥 Active Referrals:</div>`;
                    visibleRefs.forEach(ref => {
                        const status = ref.has_invested ? '💰 Invested' : `📺 ${ref.ads_watched}/30 ads`;
                        html += `<div class="active-ref-item" style="display:flex;justify-content:space-between;align-items:center;padding:6px 8px;background:rgba(0,255,135,0.03);border-radius:6px;margin-bottom:4px;border:1px solid rgba(0,255,135,0.05);"><span style="font-size:13px;color:#ccd6f0;">👤 ${ref.username}</span><span style="font-size:11px;color:#00ff87;">✅ ${status}</span></div>`;
                    });
                    if (hasMore) {
                        const hiddenCount = total - showCount;
                        html += `<div id="hiddenActiveRefs" style="display:none;">`;
                        data.active_list.slice(showCount).forEach(ref => {
                            const status = ref.has_invested ? '💰 Invested' : `📺 ${ref.ads_watched}/30 ads`;
                            html += `<div class="active-ref-item" style="display:flex;justify-content:space-between;align-items:center;padding:6px 8px;background:rgba(0,255,135,0.03);border-radius:6px;margin-bottom:4px;border:1px solid rgba(0,255,135,0.05);"><span style="font-size:13px;color:#ccd6f0;">👤 ${ref.username}</span><span style="font-size:11px;color:#00ff87;">✅ ${status}</span></div>`;
                        });
                        html += `</div><button onclick="toggleActiveReferrals()" style="width:100%;padding:8px;margin-top:6px;background:rgba(130,71,229,0.1);border:1px solid rgba(130,71,229,0.2);border-radius:6px;color:#a29bfe;font-weight:600;font-size:13px;cursor:pointer;">📋 Show all ${total} active referrals (${hiddenCount} more)</button>`;
                    }
                    listEl.innerHTML = html;
                    listEl.style.display = 'block';
                } else {
                    listEl.innerHTML = '<p style="color:#495670;font-size:13px;padding:8px 0;">No active referrals yet. Share your link!</p>';
                    listEl.style.display = 'block';
                }
            }
        }
    } catch (error) {}
}

function toggleActiveReferrals() {
    const hiddenDiv = document.getElementById('hiddenActiveRefs');
    const button = document.querySelector('button[onclick="toggleActiveReferrals()"]');
    if (hiddenDiv) {
        if (hiddenDiv.style.display === 'none' || hiddenDiv.style.display === '') {
            hiddenDiv.style.display = 'block';
            if (button) button.textContent = '🔼 Show less';
        } else {
            hiddenDiv.style.display = 'none';
            if (button) {
                const total = document.querySelectorAll('.active-ref-item').length || 0;
                const visible = 3;
                const hiddenCount = total - visible;
                if (hiddenCount > 0) button.textContent = `📋 Show all ${total} active referrals (${hiddenCount} more)`;
                else button.style.display = 'none';
            }
        }
    }
}

async function claimWelcomeBonus() {
    if (window._isBanned) return;
    const userId = tgUser ? tgUser.id : '0';
    safePopupWithCallback({
        title: '🎁 Welcome Bonus',
        message: 'Claim 0.1 USDT as a welcome bonus!\n\nNo requirements — everyone can claim! 🎉',
        buttons: [{id: 'cancel', type: 'cancel'}, {id: 'claim', type: 'ok', text: '🎁 Claim'}]
    }, async function(buttonId) {
        if (buttonId === 'claim') {
            try {
                const response = await fetch(`${API_BASE}/api/claim_welcome_bonus`, {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ telegram_id: userId })
                });
                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({}));
                    if (errorData.message && errorData.message.toLowerCase().includes('already claimed')) {
                        safePopup({ title: '✅ Already Claimed', message: 'You have already claimed your welcome bonus!', buttons: [{type: 'ok'}] });
                        loadUserData(); loadActiveReferrals(); loadTasks(); loadReferralProgress();
                        return;
                    }
                    safePopup({ title: '❌ Error', message: errorData.message || 'Something went wrong.', buttons: [{type: 'ok'}] });
                    return;
                }
                const data = await response.json();
                if (data.success === false && data.message && data.message.toLowerCase().includes('already claimed')) {
                    safePopup({ title: '✅ Already Claimed', message: 'You have already claimed your welcome bonus!', buttons: [{type: 'ok'}] });
                    loadUserData(); loadActiveReferrals(); loadTasks(); loadReferralProgress();
                    return;
                }
                if (data.success) {
                    safePopup({ title: '🎉 Bonus Claimed!', message: data.message + '\n\nNew balance: $' + data.new_balance.toFixed(2), buttons: [{type: 'ok'}] });
                    loadUserData(); loadActiveReferrals(); loadTasks(); loadReferralProgress();
                } else {
                    safePopup({ title: '❌ Error', message: data.message || 'Failed to claim bonus.', buttons: [{type: 'ok'}] });
                }
            } catch (error) {
                console.error('Error claiming bonus:', error);
                try {
                    await loadUserData();
                    const userData = await fetch(`${API_BASE}/api/user?telegram_id=${userId}`).then(r => r.json());
                    if (userData.success && userData.has_received_welcome_bonus) {
                        safePopup({ title: '✅ Bonus Claimed!', message: 'Your welcome bonus has been credited! 💰', buttons: [{type: 'ok'}] });
                        loadUserData(); loadActiveReferrals(); loadTasks(); loadReferralProgress();
                        return;
                    }
                } catch (e) {}
                safePopup({ title: '❌ Error', message: 'Network error.', buttons: [{type: 'ok'}] });
            }
        }
    });
}

async function disableInterstitialAds() {
    if (window._isBanned) return;
    const userId = tgUser ? tgUser.id : '0';
    safePopupWithCallback({
        title: '🔇 Disable Ads',
        message: 'Pay $4 USDT to reduce pop-up ads on button clicks.\n\nYou will still be able to watch rewarded ads.',
        buttons: [{id: 'cancel', type: 'cancel'}, {id: 'confirm', type: 'ok', text: '✅ Pay $4'}]
    }, async function(buttonId) {
        if (buttonId === 'confirm') {
            try {
                const response = await fetch(`${API_BASE}/api/disable_interstitial_ads`, {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ telegram_id: userId })
                });
                const data = await response.json();
                if (data.success) {
                    safePopup({ title: '✅ Ads Reduced!', message: data.message, buttons: [{type: 'ok'}] });
                    const disableBtn = document.getElementById('disableAdsBtn');
                    if (disableBtn) { disableBtn.textContent = '✅ Ads Disabled'; disableBtn.disabled = true; disableBtn.style.opacity = '0.5'; }
                    interstitialAdsDisabled = true;
                    loadUserData();
                } else {
                    safePopup({ title: '❌ Error', message: data.message || 'Failed to disable ads.', buttons: [{type: 'ok'}] });
                }
            } catch (error) {
                safePopup({ title: '❌ Error', message: 'Network error.', buttons: [{type: 'ok'}] });
            }
        }
    });
}

async function loadTasks() {
    if (window._isBanned) return;
    const userId = tgUser ? tgUser.id : '0';
    try {
        const response = await fetch(`${API_BASE}/api/tasks/${userId}`);
        const data = await response.json();
        if (data.success) {
            const tasksEl = document.getElementById('tasksList');
            if (tasksEl) {
                let html = '';
                let completedCount = 0;
                let totalTasks = 0;
                if (data.newly_completed && data.newly_completed.length > 0) {
                    const taskNames = data.newly_completed.map(id => {
                        const task = data.tasks.find(t => t.task_id === id);
                        return task ? task.title : '';
                    }).filter(Boolean);
                    if (taskNames.length > 0) {
                        safePopup({ title: '🎉 Tasks Completed!', message: 'You completed:\n• ' + taskNames.join('\n• ') + '\n\nGo to Tasks to claim your rewards!', buttons: [{type: 'ok'}] });
                    }
                }
                const visibleTasks = data.tasks.filter(task => {
                    if (task.task_id >= 8 && task.task_id <= 16) return false;
                    return !task.claimed;
                });
                totalTasks = visibleTasks.length;
                const categories = {'investments':{icon:'🌱',label:'Investments'},'referrals':{icon:'👤',label:'Referrals'},'active_referrals':{icon:'🔥',label:'Active Referrals'},'milestones':{icon:'🏆',label:'Milestones'}};
                const sortedTasks = visibleTasks.sort((a, b) => a.task_id - b.task_id);
                let currentCategory = '';
                let categoryCounts = {};
                for (const task of sortedTasks) {
                    const isCompleted = task.completed;
                    const isClaimed = task.claimed;
                    if (isCompleted && !isClaimed) completedCount++;
                    if (task.category !== currentCategory) {
                        currentCategory = task.category;
                        categoryCounts[task.category] = 0;
                        const catInfo = categories[currentCategory] || { icon: '📌', label: currentCategory };
                        html += `<div style="margin-top:16px;margin-bottom:8px;font-size:14px;font-weight:700;color:#8247E5;border-bottom:1px solid rgba(130,71,229,0.2);padding-bottom:4px;">${catInfo.icon} ${catInfo.label}</div>`;
                    }
                    categoryCounts[task.category] = (categoryCounts[task.category] || 0) + 1;
                    const currentCount = categoryCounts[task.category];
                    if (currentCount === 4 && !isCompleted) {
                        const hiddenCount = sortedTasks.filter(t => t.category === task.category && !t.claimed).length - 3;
                        if (hiddenCount > 0) {
                            html += `<button onclick="showMoreTasks('${task.category}')" style="width:100%;padding:10px;margin-bottom:8px;background:rgba(130,71,229,0.1);border:1px solid rgba(130,71,229,0.2);border-radius:8px;color:#a29bfe;font-weight:600;font-size:13px;cursor:pointer;">📋 More ${categories[task.category]?.label || task.category} tasks (${hiddenCount} remaining)...</button>`;
                        }
                    }
                    const hideTask = (currentCount > 3 && !isCompleted);
                    const userStats = data.user_stats || {};
                    let progressText = '';
                    let progressPercent = 0;
                    const conditionValue = getTaskConditionValue(task.task_id);
                    const currentValue = getTaskCurrentValue(task.task_id, userStats);
                    if (!isCompleted && conditionValue !== null && currentValue !== null) {
                        if (task.category === 'milestones') {
                            var displayValue = Math.min(currentValue, conditionValue);
                            progressText = `${Number(displayValue).toFixed(3)}/${conditionValue}`;
                        } else {
                            progressText = `${Math.round(Number(currentValue))}/${conditionValue}`;
                        }
                        progressPercent = Math.min((Number(currentValue) / conditionValue) * 100, 100);
                    } else if (isCompleted) {
                        const displayMax = conditionValue || 1;
                        progressText = `${displayMax}/${displayMax}`;
                        progressPercent = 100;
                    }
                    const statusBadge = isCompleted ? (isClaimed ? '✅ Claimed' : 'Claim Now!') : (progressText ? `⏳ ${progressText}` : '⏳ Current Task Progress');
                    const statusColor = isCompleted ? (isClaimed ? '#495670' : '#00ff87') : '#495670';
                    const rewardDisplay = task.reward < 0.01 ? '0.00' : Number(task.reward).toFixed(2);
                    const hiddenStyle = hideTask ? 'style="display:none;"' : '';
                    html += `<div class="task-item" data-category="${task.category}" data-task-id="${task.task_id}" ${hiddenStyle}>
                        <div style="background:rgba(0,0,0,0.3);border:1px solid ${isCompleted && !isClaimed ? 'rgba(0,255,135,0.3)' : 'rgba(255,255,255,0.05)'};border-radius:10px;padding:12px 14px;margin-bottom:8px;">
                            <div style="display:flex;justify-content:space-between;align-items:center;">
                                <div style="display:flex;align-items:center;gap:10px;flex:1;">
                                    <div style="font-size:20px;">${task.icon || '📌'}</div>
                                    <div style="flex:1;">
                                        <div style="font-weight:600;font-size:14px;color:${isCompleted && !isClaimed ? '#00ff87' : '#ccd6f0'};">${task.title}</div>
                                        <div style="font-size:12px;color:#8892b0;">${task.description}</div>
                                        <div style="font-size:11px;color:#ffd93d;">💰 ${rewardDisplay} USDT</div>
                                        ${!isCompleted && progressText ? `<div style="width:100%;height:4px;background:rgba(255,255,255,0.05);border-radius:2px;margin-top:4px;overflow:hidden;"><div style="width:${progressPercent}%;height:100%;background:linear-gradient(90deg,#8247E5,#00ff87);border-radius:2px;"></div></div>` : ''}
                                    </div>
                                </div>
                                <div style="text-align:right;">
                                    <div style="font-size:11px;color:${statusColor};">${statusBadge}</div>
                                    ${isCompleted && !isClaimed ? `<button onclick="claimTaskReward(${task.task_id})" style="margin-top:4px;padding:6px 12px;background:linear-gradient(135deg,#00ff87,#00cc6a);border:none;border-radius:6px;color:#0a0e17;font-weight:700;font-size:13px;cursor:pointer;">💰 Claim</button>` : ''}
                                </div>
                            </div>
                        </div>
                    </div>`;
                }
                if (totalTasks === 0) {
                    html = `<div style="text-align:center;padding:30px 20px;background:rgba(0,255,135,0.05);border-radius:12px;border:1px solid rgba(0,255,135,0.1);"><div style="font-size:48px;margin-bottom:10px;">🎉</div><div style="font-size:18px;font-weight:700;color:#00ff87;">All Tasks Completed!</div><div style="font-size:13px;color:#8892b0;margin-top:4px;">You've completed all tasks!</div></div>`;
                }
                tasksEl.innerHTML = html;
                const progressEl = document.getElementById('taskProgress');
                if (progressEl) {
                    const total = data.stats.total_tasks || 0;
                    const done = data.stats.completed_tasks || 0;
                    progressEl.textContent = `${done}/${total} tasks completed`;
                    progressEl.style.color = done === total ? '#00ff87' : '#ccd6f0';
                }
            }
        }
    } catch (error) {}
}

function showMoreTasks(category) {
    if (window._isBanned) return;
    const taskItems = document.querySelectorAll(`.task-item[data-category="${category}"]`);
    const button = document.querySelector(`button[onclick*="showMoreTasks('${category}')"]`);
    if (button) button.style.display = 'none';
    taskItems.forEach(item => {
        if (item.style.display === 'none' || !item.style.display) {
            item.style.display = 'block';
            item.style.animation = 'fadeIn 0.3s ease';
        }
    });
}

function getTaskConditionValue(taskId) {
    const taskConditions = {1:1,2:10,3:50,4:100,5:200,6:500,7:1000,17:1,18:3,19:5,20:10,21:25,22:50,23:100,24:250,25:500,26:1000,27:1,28:3,29:5,30:10,31:25,32:50,33:100,34:250,35:500,36:1000,37:1,38:10,39:25,40:50,41:100,42:250,43:500,44:1000};
    return taskConditions[taskId] || null;
}

function getTaskCurrentValue(taskId, userStats) {
    const taskCurrentValues = {
        1: userStats.has_invested ? 1 : 0,
        2: Number(userStats.total_invested) || 0,
        3: Number(userStats.total_invested) || 0,
        4: Number(userStats.total_invested) || 0,
        5: Number(userStats.total_invested) || 0,
        6: Number(userStats.total_invested) || 0,
        7: Number(userStats.total_invested) || 0,
        17: Number(userStats.total_referrals) || 0, 18: Number(userStats.total_referrals) || 0,
        19: Number(userStats.total_referrals) || 0, 20: Number(userStats.total_referrals) || 0,
        21: Number(userStats.total_referrals) || 0, 22: Number(userStats.total_referrals) || 0,
        23: Number(userStats.total_referrals) || 0, 24: Number(userStats.total_referrals) || 0,
        25: Number(userStats.total_referrals) || 0, 26: Number(userStats.total_referrals) || 0,
        27: Number(userStats.total_active_referrals) || 0, 28: Number(userStats.total_active_referrals) || 0,
        29: Number(userStats.total_active_referrals) || 0, 30: Number(userStats.total_active_referrals) || 0,
        31: Number(userStats.total_active_referrals) || 0, 32: Number(userStats.total_active_referrals) || 0,
        33: Number(userStats.total_active_referrals) || 0, 34: Number(userStats.total_active_referrals) || 0,
        35: Number(userStats.total_active_referrals) || 0, 36: Number(userStats.total_active_referrals) || 0,
        37: Number(userStats.total_earnings) || 0, 38: Number(userStats.total_earnings) || 0,
        39: Number(userStats.total_earnings) || 0, 40: Number(userStats.total_earnings) || 0,
        41: Number(userStats.total_earnings) || 0, 42: Number(userStats.total_earnings) || 0,
        43: Number(userStats.total_earnings) || 0, 44: Number(userStats.total_earnings) || 0
    };
    const value = taskCurrentValues[taskId];
    return typeof value === 'number' ? value : 0;
}

async function claimTaskReward(taskId) {
    if (window._isBanned) return;
    const userId = tgUser ? tgUser.id : '0';
    if (window.claimingInProgress) return;
    safePopupWithCallback({
        title: '💰 Claim Reward',
        message: 'Claim your reward for completing this task?',
        buttons: [{id:'cancel',type:'cancel'},{id:'confirm',type:'ok',text:'💰 Claim'}]
    }, async function(buttonId) {
        if (buttonId === 'confirm') {
            window.claimingInProgress = true;
            try {
                const response = await fetch(`${API_BASE}/api/claim_task_reward`, {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ telegram_id: userId, task_id: taskId })
                });
                const data = await response.json();
                if (data.success === false && data.message === "Task not found") {
                    safePopup({ title: '✅ Already Claimed!', message: 'This task was already claimed.', buttons: [{type: 'ok'}] });
                    loadTasks(); loadUserData();
                    window.claimingInProgress = false;
                    return;
                }
                if (data.success) {
                    const reward = parseFloat(data.message.match(/\d+\.?\d*/)?.[0] || '0');
                    const rewardDisplay = reward < 0.01 ? '0.00' : reward.toFixed(2);
                    safePopup({ title: '🎉 Reward Claimed!', message: 'Claimed $' + rewardDisplay + ' USDT!\n\nNew balance: $' + data.new_balance.toFixed(2), buttons: [{type: 'ok'}] });
                    loadTasks();
                    loadUserData();
                } else {
                    safePopup({ title: '❌ Error', message: data.message || 'Failed to claim reward.', buttons: [{type: 'ok'}] });
                }
            } catch (error) {
                safePopup({ title: 'ℹ️ Check Your Balance', message: 'Please refresh to see if your reward was credited.', buttons: [{type: 'ok'}] });
                loadTasks();
                loadUserData();
            } finally {
                window.claimingInProgress = false;
            }
        }
    });
}

let referralListExpanded = false;

async function loadReferralProgress() {
    if (window._isBanned) return;
    const userId = tgUser ? tgUser.id : '0';
    try {
        const response = await fetch(`${API_BASE}/api/get_referral_progress/${userId}`);
        const data = await response.json();
        const container = document.getElementById('referralProgressTable');
        const showMoreBtn = document.getElementById('showMoreReferralsBtn');
        if (!container) return;
        if (!data.success) {
            container.innerHTML = '<tr><td colspan="4" style="text-align:center;padding:10px;color:#8892b0;">No referrals yet.</td></tr>';
            return;
        }
        const referrals = data.referrals || [];
        if (referrals.length === 0) {
            container.innerHTML = '<tr><td colspan="4" style="text-align:center;padding:10px;color:#8892b0;">No referrals yet. Share your link!</td></tr>';
            return;
        }
        const showCount = referralListExpanded ? referrals.length : 5;
        const visible = referrals.slice(0, showCount);
        const hasMore = referrals.length > 5;
        let html = '';
        visible.forEach(ref => {
            const walletStatus = ref.wallet_connected ? '✅' : '❌';
            const adsStatus = ref.ads_watched >= 3 ? '✅ 3/3' : `${ref.ads_watched}/3`;
            const rewardStatus = ref.reward_claimed ? '✅ Claimed' : '⏳ Pending';
            const statusColor = ref.reward_claimed ? '#00ff87' : '#ffd93d';
            html += `<tr style="border-bottom:1px solid rgba(255,255,255,0.03);"><td style="padding:6px 4px;color:#ccd6f0;">${ref.username}</td><td style="text-align:center;padding:6px 4px;">${walletStatus}</td><td style="text-align:center;padding:6px 4px;color:#8892b0;">${adsStatus}</td><td style="text-align:right;padding:6px 4px;color:${statusColor};">${rewardStatus}</td></tr>`;
        });
        container.innerHTML = html;
        if (showMoreBtn) {
            if (hasMore) {
                showMoreBtn.style.display = 'block';
                showMoreBtn.textContent = referralListExpanded ? '🔼 Show less' : `📋 Show all ${referrals.length} →`;
            } else {
                showMoreBtn.style.display = 'none';
            }
        }
    } catch (error) {
        const container = document.getElementById('referralProgressTable');
        if (container) container.innerHTML = '<tr><td colspan="4" style="text-align:center;padding:10px;color:#ff6b6b;">Error loading referral progress.</td></tr>';
    }
}

function toggleReferralList() {
    referralListExpanded = !referralListExpanded;
    loadReferralProgress();
}

window.navigateTo = navigateTo;
window.goBack = goBack;
window.refreshData = refreshData;
window.copyAddress = copyAddress;
window.copyReferral = copyReferral;
window.claimReferralRewards = claimReferralRewards;
window.checkDeposit = checkDeposit;
window.checkDepositWithAmount = checkDepositWithAmount;
window.investField = investField;
window.investFieldWithLock = investFieldWithLock;
window.filterHistory = filterHistory;
window.saveWallet = saveWallet;
window.disconnectWallet = disconnectWallet;
window.setWallet = setWallet;
window.watchRewardedAd = watchRewardedAd;
window.canWatchAd = canWatchAd;
window.loadAdStats = loadAdStats;
window.claimInvestment = claimInvestment;
window.showInterstitialIfNeeded = showInterstitialIfNeeded;
window.upgradeReferralTier = upgradeReferralTier;
window.loadActiveReferrals = loadActiveReferrals;
window.toggleActiveReferrals = toggleActiveReferrals;
window.claimWelcomeBonus = claimWelcomeBonus;
window.disableInterstitialAds = disableInterstitialAds;
window.loadTasks = loadTasks;
window.claimTaskReward = claimTaskReward;
window.showMoreTasks = showMoreTasks;
window.loadReferralProgress = loadReferralProgress;
window.toggleReferralList = toggleReferralList;
window.selectCurrency = selectCurrency;
window.isValidTonAddress = isValidTonAddress;
window.showBanScreen = showBanScreen;

console.log('✅ PlantUSDT app loaded successfully (v73)');
console.log('📢 Welcome bonus: 0.1 USDT — everyone can claim!');
console.log('🎁 Referral reward: $0.005 when friend connects wallet + watches 3 ads');
console.log('💰 Available Earnings button: shows unclaimed referral rewards');
console.log('🔥 Active Referrals tracked silently for ambassador promotion');
console.log('📺 Ads fund weekly community giveaways — no per-ad reward');
console.log('🚫 Ban system active — banned users see suspension notice');
console.log('🛡️ Fingerprint + real IP capture active for abuse detection');
console.log('📊 Task rewards display 2 decimals (no more 0.010)');
console.log('💳 Withdrawal fees: 15% / 18% / 20%');
console.log('🔒 Duplicate wallet protection active');
console.log('🎯 Math captcha accepts 0 as valid answer');
console.log('💰 Pending referral rewards accumulate until claimed');
console.log('📋 Referral progress table shows wallet + 3 ads status');
console.log('🔄 No more auto-timer — giveaway drawn manually by admin');
console.log('🎨 UI cleaned: no giveaway pool display, no active referral bonus row');
