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

// ============================================
// SAFE POPUP – Works on both Web & Mobile
// ============================================
function safePopup(options) {
    try {
        if (typeof tg !== 'undefined' && tg.showPopup) {
            tg.showPopup(options);
        } else {
            const message = typeof options === 'string' 
                ? options 
                : options.title + '\n\n' + options.message;
            alert(message);
        }
    } catch (e) {
        alert(options.message || options);
    }
}

function safePopupWithCallback(options, callback) {
    try {
        if (typeof tg !== 'undefined' && tg.showPopup) {
            tg.showPopup(options, callback);
        } else {
            const message = options.title + '\n\n' + options.message;
            if (confirm(message)) {
                if (callback) callback('confirm');
            } else {
                if (callback) callback('cancel');
            }
        }
    } catch (e) {
        alert(options.message || options);
        if (callback) callback('confirm');
    }
}

// ============================================
// SHOW INTERSTITIAL AD ON BUTTON CLICKS
// ============================================
function showInterstitialIfNeeded() {
    if (interstitialAdsDisabled) {
        console.log("🔇 Interstitial ads disabled by user");
        return;
    }
    
    var now = Date.now();
    if (now - lastAdTime < AD_COOLDOWN) {
        console.log("⏳ Ad cooldown active, skipping...");
        return;
    }
    lastAdTime = now;

    if (window.showInterstitialAd && typeof window.showInterstitialAd === 'function') {
        console.log("📢 Showing interstitial ad on button click...");
        setTimeout(function() {
            window.showInterstitialAd().catch(() => {});
        }, 500);
    }
}

// ============================================
// PAGE NAVIGATION
// ============================================
document.addEventListener('DOMContentLoaded', function() {
    tg.ready();
    tg.expand();
    loadUserData();
    loadSavedWallet();
    setupEventListeners();
    startCountdownTimer();
    loadAdStats();
    loadActiveReferrals();
    loadTasks();

    document.addEventListener('click', function(e) {
        var target = e.target.closest('button');
        if (!target) return;

        if (target.classList.contains('back-btn') || 
            target.classList.contains('no-ad') || 
            target.id === 'watchAdBtn') {
            return;
        }

        if (target.type === 'submit' && target.closest('#withdrawForm')) {
            return;
        }

        showInterstitialIfNeeded();
    });
});

function navigateTo(page) {
    const pages = {
        'dashboard': 'dashboard.html',
        'deposit': 'deposit.html',
        'withdraw': 'withdraw.html',
        'history': 'history.html',
        'index': 'index.html'
    };
    if (pages[page]) {
        showInterstitialIfNeeded();
        window.location.href = pages[page];
    }
}

function goBack() {
    window.history.back();
}

// ============================================
// USER DATA
// ============================================
async function loadUserData() {
    try {
        const userId = tgUser ? tgUser.id : '0';
        const response = await fetch(`${API_BASE}/api/user?telegram_id=${userId}`);
        const data = await response.json();
        if (data.success) {
            interstitialAdsDisabled = data.interstitial_ads_disabled || false;
            console.log('📢 interstitial_ads_disabled:', interstitialAdsDisabled);
            
            updateUI(data);
            updateFields(data);
            updateReferral(data);
            updateDashboardUI(data);
            await updateReferralStats(userId);
            await updateWelcomeBonusButton(data);
            updateTierButtons(data);
            
            if (data.interstitial_ads_disabled) {
                const disableBtn = document.getElementById('disableAdsBtn');
                if (disableBtn) {
                    disableBtn.textContent = '✅ Ads Disabled';
                    disableBtn.disabled = true;
                    disableBtn.style.opacity = '0.5';
                }
            }
        }
    } catch (error) {
        console.error('Error loading user data:', error);
    }
}

function refreshData() {
    showInterstitialIfNeeded();
    var balanceEl = document.getElementById('balance');
    var totalEarningsEl = document.getElementById('totalEarnings');

    if (balanceEl) {
        balanceEl.textContent = '⏳ ...';
    }
    if (totalEarningsEl) {
        totalEarningsEl.textContent = '⏳ ...';
    }

    setTimeout(function() {
        loadUserData();
        loadSavedWallet();
        loadAdStats();
        loadActiveReferrals();
        loadTasks();
    }, 300);
}

async function updateReferralStats(userId) {
    try {
        const response = await fetch(`${API_BASE}/api/referral_stats/${userId}`);
        const data = await response.json();
        if (data.success) {
            var referralCountEl = document.getElementById('referralCount');
            var referralEarnedEl = document.getElementById('referralEarned');
            var level1CountEl = document.getElementById('level1Count');
            var level1EarningsEl = document.getElementById('level1Earnings');

            if (referralCountEl) referralCountEl.textContent = data.total_referrals || 0;
            if (referralEarnedEl) referralEarnedEl.textContent = '$' + Number(data.total_earnings || 0).toFixed(3);
            if (level1CountEl) level1CountEl.textContent = data.level1_count || 0;
            if (level1EarningsEl) level1EarningsEl.textContent = '$' + Number(data.level1_earnings || 0).toFixed(3);
        }
    } catch (error) {
        console.error('Error loading referral stats:', error);
    }
}

function updateUI(data) {
    var balanceEl = document.getElementById('balance');
    if (balanceEl) {
        balanceEl.textContent = '$' + Number(data.balance || 0).toFixed(3);
    }

    var totalEarningsEl = document.getElementById('totalEarnings');
    if (totalEarningsEl) {
        totalEarningsEl.textContent = '$' + Number(data.total_earnings || 0).toFixed(3);
    }

    var investmentEarningsEl = document.getElementById('investmentEarnings');
    if (investmentEarningsEl) {
        investmentEarningsEl.textContent = '$' + Number(data.investment_earnings || 0).toFixed(3);
    }

    var referralEarningsDisplayEl = document.getElementById('referralEarningsDisplay');
    if (referralEarningsDisplayEl) {
        referralEarningsDisplayEl.textContent = '$' + Number(data.referral_earned || 0).toFixed(3);
    }

    var adEarningsDisplayEl = document.getElementById('adEarningsDisplay');
    if (adEarningsDisplayEl) {
        adEarningsDisplayEl.textContent = '$' + Number(data.total_ad_earnings || 0).toFixed(3);
    }

    var tasksEarningsDisplayEl = document.getElementById('tasksEarningsDisplay');
    if (tasksEarningsDisplayEl) {
        tasksEarningsDisplayEl.textContent = '$' + Number(data.tasks_earnings || 0).toFixed(3);
    }
}

function updateDashboardUI(data) {
    var dashBalance = document.getElementById('dashBalance');
    var dashInvested = document.getElementById('dashInvested');
    var dashEarned = document.getElementById('dashEarned');
    var dashDeposited = document.getElementById('dashDeposited');
    var dashReferrals = document.getElementById('dashReferrals');
    var dashAdEarnings = document.getElementById('dashAdEarnings');
    var dashTasksEarnings = document.getElementById('dashTasksEarnings');

    if (dashBalance) dashBalance.textContent = '$' + Number(data.balance || 0).toFixed(3);
    if (dashInvested) dashInvested.textContent = '$' + Number(data.total_invested || 0).toFixed(3);
    if (dashEarned) dashEarned.textContent = '$' + Number(data.total_earnings || 0).toFixed(3);
    if (dashDeposited) dashDeposited.textContent = '$' + Number(data.total_deposited || 0).toFixed(3);
    if (dashReferrals) dashReferrals.textContent = data.referrals || 0;
    if (dashAdEarnings) dashAdEarnings.textContent = '$' + Number(data.total_ad_earnings || 0).toFixed(3);
    if (dashTasksEarnings) dashTasksEarnings.textContent = '$' + Number(data.tasks_earnings || 0).toFixed(3);
}

// ============================================
// WELCOME BONUS BUTTON
// ============================================
function updateWelcomeBonusButton(data) {
    const btn = document.getElementById('claimWelcomeBtn');
    if (!btn) {
        return;
    }
    
    if (data.has_received_welcome_bonus) {
        btn.textContent = '✅ Claimed (0.1 USDT)';
        btn.disabled = true;
        btn.style.opacity = '0.7';
        btn.style.cursor = 'default';
        btn.style.background = 'rgba(0,255,135,0.1)';
        btn.style.border = '1px solid rgba(0,255,135,0.2)';
        btn.style.color = '#00ff87';
    } else {
        btn.textContent = '🎁 Claim Welcome Bonus (0.1 USDT)';
        btn.disabled = false;
        btn.style.opacity = '1';
        btn.style.cursor = 'pointer';
        btn.style.background = 'linear-gradient(135deg, #ffd93d, #f9a825)';
        btn.style.border = 'none';
        btn.style.color = '#0a0e17';
    }
}

// ============================================
// REFERRAL TIER DISPLAY
// ============================================

function updateTierButtons(data) {
    const userTier = data.referral_tier || 'free';
    console.log('📊 User tier:', userTier);
    
    const tierCards = document.querySelectorAll('.tier-card');
    tierCards.forEach(card => {
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
            const tierOrder = ['free', 'bronze', 'silver', 'gold', 'diamond'];
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

// ============================================
// FIELDS
// ============================================
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

        if (!statusEl || !amountEl || !daysEl || !earnedEl || !progressEl || !cardEl || !btnEl || !timerEl) {
            continue;
        }

        var field = fields.find(function(f) { return f.field_number === i; });

        if (field) {
            var lockPeriod = field.lock_period || 30;
            var isLocked = field.is_locked || false;
            var unlockDate = new Date(field.unlock_date);
            var now = new Date();
            var daysRemaining = Math.max(0, Math.ceil((unlockDate - now) / (1000 * 60 * 60 * 24)));

            window.fieldData[i] = {
                unlock_date: field.unlock_date,
                is_locked: isLocked,
                lock_period: lockPeriod,
                is_ready: false
            };

            amountEl.textContent = '$' + field.amount.toFixed(3);
            daysEl.textContent = isLocked ? daysRemaining + '/' + lockPeriod + ' days' : lockPeriod + '/' + lockPeriod + ' days';

            var displayEarned = isLocked ? field.expected_return || 0 : field.paid_out || 0;
            earnedEl.textContent = '$' + displayEarned.toFixed(3);

            var progress = isLocked ? ((lockPeriod - daysRemaining) / lockPeriod) * 100 : 100;
            progressEl.style.width = Math.min(progress, 100) + '%';
            cardEl.className = 'field-card active';

            btnEl.textContent = '🔒 Locked';
            btnEl.disabled = true;
            btnEl.style.opacity = '0.5';
            btnEl.style.cursor = 'not-allowed';
            btnEl.style.background = '';
            btnEl.style.color = '';
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
            btnEl.style.background = '';
            btnEl.style.color = '';
            btnEl.onclick = (function(fieldNum) {
                return function() { 
                    showInterstitialIfNeeded(); 
                    investField(fieldNum); 
                };
            })(i);
            window.fieldData[i] = null;
        }
    }
}

// ============================================
// CLAIM INVESTMENT
// ============================================
async function claimInvestment(fieldNumber) {
    console.log('🔍 Claim button clicked for Field #' + fieldNumber);

    if (window.claimInProgress) {
        console.log('⏳ Claim already in progress...');
        return;
    }
    window.claimInProgress = true;

    const userId = tgUser ? tgUser.id : '0';
    if (!userId || userId === '0') {
        safePopup({
            title: '❌ Error',
            message: 'User not authenticated. Please restart the app.',
            buttons: [{type: 'ok'}]
        });
        window.claimInProgress = false;
        return;
    }

    safePopupWithCallback({
        title: '🌾 Claim Investment',
        message: 'Are you sure you want to claim Field #' + fieldNumber + '?',
        buttons: [
            {id: 'cancel', type: 'cancel'},
            {id: 'confirm', type: 'ok', text: '✅ Claim'}
        ]
    }, async function(buttonId) {
        if (buttonId === 'confirm') {
            try {
                console.log('📤 Sending claim request for Field #' + fieldNumber);

                const response = await fetch(`${API_BASE}/api/claim_investment`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        telegram_id: userId,
                        field_number: fieldNumber
                    })
                });

                const data = await response.json();
                console.log('📥 Claim response:', data);

                if (data.success) {
                    safePopup({
                        title: '✅ Claimed!',
                        message: 'You claimed $' + data.amount.toFixed(2) + ' USDT from Field #' + fieldNumber + '!\n\n🌱 The field is now available for a new investment.',
                        buttons: [{type: 'ok'}]
                    });

                    setTimeout(function() {
                        if (window.watchRewardedAd) {
                            console.log("📢 Showing rewarded ad after claim...");
                            window.watchRewardedAd();
                        }
                        setTimeout(function() {
                            loadUserData();
                            loadAdStats();
                            loadActiveReferrals();
                            loadTasks();
                            window.claimInProgress = false;
                        }, 3000);
                    }, 1000);

                } else {
                    safePopup({
                        title: '❌ Error',
                        message: data.message || 'Failed to claim.',
                        buttons: [{type: 'ok'}]
                    });
                    window.claimInProgress = false;
                }
            } catch (error) {
                console.error('❌ Error claiming:', error);
                safePopup({
                    title: '❌ Error',
                    message: 'Network error. Please try again.',
                    buttons: [{type: 'ok'}]
                });
                window.claimInProgress = false;
            }
        } else {
            window.claimInProgress = false;
        }
    });
}

// ============================================
// TIMERS
// ============================================
function updateFieldTimers() {
    if (document.getElementById('historyList')) {
        return;
    }

    var now = new Date();
    var utcNow = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate(), now.getUTCHours(), now.getUTCMinutes(), now.getUTCSeconds());

    for (var i = 1; i <= 3; i++) {
        var timerEl = document.getElementById('field' + i + 'Timer');
        var statusEl = document.getElementById('field' + i + 'Status');
        var btnEl = document.getElementById('field' + i + 'Btn');

        if (!timerEl || !statusEl || !btnEl) continue;

        var fieldData = window.fieldData ? window.fieldData[i] : null;
        if (!fieldData || !fieldData.unlock_date) {
            timerEl.textContent = '⏳ Payout: --:--:-- UTC';
            timerEl.className = 'field-timer';
            continue;
        }

        var isLocked = fieldData.is_locked === true;
        var lockPeriod = fieldData.lock_period || 30;

        var unlockDateStr = fieldData.unlock_date;
        if (unlockDateStr.endsWith('Z')) {
            unlockDateStr = unlockDateStr.slice(0, -1);
        }
        var unlockDate = new Date(unlockDateStr + 'Z').getTime();
        var timeLeft = unlockDate - utcNow;

        var isReady = (isLocked === true) && (timeLeft <= 0);
        fieldData.is_ready = isReady;

        if (isReady) {
            timerEl.textContent = '🟢 READY TO CLAIM!';
            timerEl.className = 'field-timer ready';
            timerEl.style.color = '#ffd93d';
            timerEl.style.borderColor = 'rgba(255, 217, 61, 0.3)';
            timerEl.style.background = 'rgba(255, 217, 61, 0.1)';
            timerEl.style.animation = 'pulse-gold 1.5s infinite';

            btnEl.textContent = '🌾 Claim Now!';
            btnEl.disabled = false;
            btnEl.style.opacity = '1';
            btnEl.style.cursor = 'pointer';
            btnEl.style.background = 'linear-gradient(135deg, #ffd93d, #f9a825)';
            btnEl.style.color = '#0a0e17';
            btnEl.style.border = 'none';
            btnEl.onclick = (function(fieldNum) {
                return function() { 
                    console.log('🖱️ Claim button clicked for Field #' + fieldNum);
                    claimInvestment(fieldNum); 
                };
            })(i);

            statusEl.textContent = '✅ Ready to Claim!';
            statusEl.className = 'field-status ready';
            statusEl.style.color = '#ffd93d';

        } else if (isLocked === true && timeLeft > 0) {
            var days = Math.floor(timeLeft / (1000 * 60 * 60 * 24));
            var hours = Math.floor((timeLeft % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
            var minutes = Math.floor((timeLeft % (1000 * 60 * 60)) / (1000 * 60));
            var seconds = Math.floor((timeLeft % (1000 * 60)) / 1000);

            var timeString = '';
            if (days > 0) {
                timeString = days + 'd ' + String(hours).padStart(2, '0') + ':' + String(minutes).padStart(2, '0') + ':' + String(seconds).padStart(2, '0');
            } else {
                timeString = String(hours).padStart(2, '0') + ':' + String(minutes).padStart(2, '0') + ':' + String(seconds).padStart(2, '0');
            }
            timerEl.textContent = '🔄 Unlock in: ' + timeString + ' UTC';
            timerEl.className = 'field-timer countdown';
            timerEl.style.color = '';
            timerEl.style.borderColor = '';
            timerEl.style.background = '';
            timerEl.style.animation = '';

            btnEl.textContent = '🔒 Locked';
            btnEl.disabled = true;
            btnEl.style.opacity = '0.5';
            btnEl.style.cursor = 'not-allowed';
            btnEl.style.background = '';
            btnEl.style.color = '';
            btnEl.onclick = null;

            statusEl.textContent = '🔒 Locked';
            statusEl.className = 'field-status locked';
            statusEl.style.color = '#ff6b6b';

        } else if (isLocked === false) {
            timerEl.textContent = '🟢 Available (UTC)';
            timerEl.className = 'field-timer';
            timerEl.style.color = '';
            timerEl.style.borderColor = '';
            timerEl.style.background = '';
            timerEl.style.animation = '';

            btnEl.textContent = '🌱 Plant Now';
            btnEl.disabled = false;
            btnEl.style.opacity = '1';
            btnEl.style.cursor = 'pointer';
            btnEl.style.background = '';
            btnEl.style.color = '';
            btnEl.onclick = (function(fieldNum) {
                return function() { 
                    showInterstitialIfNeeded(); 
                    investField(fieldNum); 
                };
            })(i);

            statusEl.textContent = '✅ Available';
            statusEl.className = 'field-status available';
            statusEl.style.color = '#8247E5';
        }
    }
}

var style = document.createElement('style');
style.textContent = `
    @keyframes pulse-gold {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }
`;
document.head.appendChild(style);

function startCountdownTimer() {
    updateFieldTimers();
    if (timerInterval) {
        clearInterval(timerInterval);
    }
    timerInterval = setInterval(updateFieldTimers, 1000);
}

function stopCountdownTimer() {
    if (timerInterval) {
        clearInterval(timerInterval);
        timerInterval = null;
    }
}

// ============================================
// REFERRAL
// ============================================
async function updateReferral(data) {
    var referralLink = document.getElementById('referralLinkText');
    var walletText = document.getElementById('walletText');
    var isConnected = walletText ? walletText.textContent.includes('Connected') : false;

    if (referralLink) {
        if (isConnected) {
            var userId = tgUser ? tgUser.id : '0';
            try {
                var response = await fetch(API_BASE + '/api/get_referral_code?telegram_id=' + userId + '&t=' + Date.now());
                var result = await response.json();
                if (result.success && result.referral_code) {
                    referralLink.textContent = 'https://t.me/PlantUSDT_bot?start=' + result.referral_code;
                    referralLink.style.color = '#ccd6f0';
                } else {
                    referralLink.textContent = 'Error loading referral link';
                }
            } catch (error) {
                referralLink.textContent = 'Error loading referral link';
            }
        } else {
            referralLink.textContent = '⚠️ Save wallet to get referral link';
            referralLink.style.color = '#ff6b6b';
        }
    }
}

// ============================================
// COPY REFERRAL FUNCTION
// ============================================
async function copyReferral() {
    showInterstitialIfNeeded();
    
    var userId = tgUser ? tgUser.id : '0';
    var referralLinkEl = document.getElementById('referralLinkText');
    var referralLink = referralLinkEl ? referralLinkEl.textContent.trim() : '';
    
    if (!referralLink || referralLink.includes('Loading') || referralLink.includes('Error') || referralLink.includes('⚠️')) {
        try {
            var response = await fetch(API_BASE + '/api/get_referral_code?telegram_id=' + userId + '&t=' + Date.now());
            var data = await response.json();
            if (data.success && data.referral_code) {
                referralLink = 'https://t.me/PlantUSDT_bot?start=' + data.referral_code;
                if (referralLinkEl) {
                    referralLinkEl.textContent = referralLink;
                }
            } else {
                safePopup({
                    title: '❌ Error',
                    message: 'Could not get referral link. Please try again.',
                    buttons: [{type: 'ok'}]
                });
                return;
            }
        } catch (error) {
            console.error('Error getting referral code:', error);
            safePopup({
                title: '❌ Error',
                message: 'Network error. Please try again.',
                buttons: [{type: 'ok'}]
            });
            return;
        }
    }
    
    if (referralLink.includes('Save wallet') || referralLink.includes('wallet not connected')) {
        safePopup({
            title: '⚠️ Wallet Required',
            message: 'Please save your Polygon wallet address first to get your referral link!',
            buttons: [{type: 'ok'}]
        });
        return;
    }

    if (!referralLink.startsWith('https://t.me/PlantUSDT_bot?start=')) {
        safePopup({
            title: '❌ Error',
            message: 'Invalid referral link. Please try again.',
            buttons: [{type: 'ok'}]
        });
        return;
    }

    try {
        await navigator.clipboard.writeText(referralLink);
        safePopup({
            title: '✅ Copied!',
            message: 'Referral link copied to clipboard!\n\nShare it with your friends and earn up to 5% of their deposits! 🎉',
            buttons: [{type: 'ok'}]
        });
    } catch (clipError) {
        var textArea = document.createElement('textarea');
        textArea.value = referralLink;
        document.body.appendChild(textArea);
        textArea.select();
        try {
            document.execCommand('copy');
            safePopup({
                title: '✅ Copied!',
                message: 'Referral link copied to clipboard!\n\nShare it with your friends and earn up to 5% of their deposits! 🎉',
                buttons: [{type: 'ok'}]
            });
        } catch (fallbackError) {
            safePopup({
                title: '📋 Your Referral Link',
                message: referralLink,
                buttons: [{type: 'ok'}]
            });
        }
        document.body.removeChild(textArea);
    }
}

// ============================================
// WALLET FUNCTIONS
// ============================================
async function saveWallet() {
    showInterstitialIfNeeded();
    var userId = tgUser ? tgUser.id : '0';
    var walletInput = document.getElementById('walletInput');
    var walletAddress = walletInput ? walletInput.value.trim() : '';
    if (!walletAddress) {
        safePopup({title:'❌ Error', message:'Please enter a Polygon wallet address.', buttons:[{type:'ok'}]});
        return;
    }
    if (!walletAddress.startsWith('0x') || walletAddress.length !== 42) {
        safePopup({title:'❌ Invalid Address', message:'Please enter a valid Polygon wallet address.', buttons:[{type:'ok'}]});
        return;
    }
    if (walletAddress.toLowerCase() === PROJECT_WALLET.toLowerCase()) {
        safePopup({title:'❌ Invalid Wallet', message:'This is the project wallet on Polygon. Please enter your own.', buttons:[{type:'ok'}]});
        return;
    }
    try {
        var response = await fetch(API_BASE + '/api/save_wallet', {
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body:JSON.stringify({telegram_id:userId, wallet_address:walletAddress})
        });
        var data = await response.json();
        if (data.success) {
            safePopup({title:'✅ Wallet Saved!', message:'Polygon wallet saved: ' + walletAddress.slice(0,6) + '...' + walletAddress.slice(-4), buttons:[{type:'ok'}]});
            updateWalletUI(walletAddress);
            loadUserData();
        } else {
            safePopup({title:'❌ Error', message:data.message || 'Failed to save wallet.', buttons:[{type:'ok'}]});
        }
    } catch (error) {
        console.error('Error saving wallet:', error);
        safePopup({title:'❌ Error', message:'Failed to save wallet. Please try again.', buttons:[{type:'ok'}]});
    }
}

function updateWalletUI(address) {
    var statusText = document.getElementById('walletText');
    var addressDisplay = document.getElementById('walletAddressDisplay');
    var walletInput = document.getElementById('walletInput');
    var saveBtn = document.getElementById('saveWalletBtn');
    var disconnectBtn = document.getElementById('disconnectWalletBtn');
    if (statusText) {
        statusText.textContent = '✅ Polygon Wallet Connected';
        statusText.className = 'connected';
    }
    if (addressDisplay) {
        addressDisplay.textContent = '📍 ' + address + ' (Polygon)';
        addressDisplay.style.display = 'block';
    }
    if (walletInput) {
        walletInput.value = address;
        walletInput.disabled = true;
        walletInput.style.opacity = '0.6';
    }
    if (saveBtn) saveBtn.style.display = 'none';
    if (disconnectBtn) disconnectBtn.style.display = 'flex';
    loadUserData();
}

function resetWalletUI() {
    var statusText = document.getElementById('walletText');
    var addressDisplay = document.getElementById('walletAddressDisplay');
    var walletInput = document.getElementById('walletInput');
    var saveBtn = document.getElementById('saveWalletBtn');
    var disconnectBtn = document.getElementById('disconnectWalletBtn');
    if (statusText) {
        statusText.textContent = 'Polygon wallet not connected';
        statusText.className = 'disconnected';
    }
    if (addressDisplay) addressDisplay.style.display = 'none';
    if (walletInput) {
        walletInput.value = '';
        walletInput.disabled = false;
        walletInput.style.opacity = '1';
    }
    if (saveBtn) saveBtn.style.display = 'flex';
    if (disconnectBtn) disconnectBtn.style.display = 'none';
    loadUserData();
}

async function disconnectWallet() {
    showInterstitialIfNeeded();
    var userId = tgUser ? tgUser.id : '0';
    safePopupWithCallback({
        title:'🔓 Disconnect Wallet',
        message:'Are you sure you want to disconnect your Polygon wallet?',
        buttons:[
            {id:'cancel', type:'cancel'},
            {id:'confirm', type:'ok', text:'Disconnect'}
        ]
    }, async function(buttonId) {
        if (buttonId === 'confirm') {
            try {
                var response = await fetch(API_BASE + '/api/save_wallet', {
                    method:'POST',
                    headers:{'Content-Type':'application/json'},
                    body:JSON.stringify({telegram_id:userId, wallet_address:''})
                });
                var data = await response.json();
                if (data.success) {
                    resetWalletUI();
                    safePopup({title:'✅ Disconnected', message:'Polygon wallet disconnected.', buttons:[{type:'ok'}]});
                } else {
                    safePopup({title:'❌ Error', message:'Failed to disconnect.', buttons:[{type:'ok'}]});
                }
            } catch (error) {
                console.error('Error disconnecting wallet:', error);
                safePopup({title:'❌ Error', message:'Failed to disconnect. Please try again.', buttons:[{type:'ok'}]});
            }
        }
    });
}

async function loadSavedWallet() {
    var userId = tgUser ? tgUser.id : '0';
    try {
        var response = await fetch(API_BASE + '/api/get_wallet?telegram_id=' + userId);
        var data = await response.json();
        if (data.success && data.wallet_address) {
            updateWalletUI(data.wallet_address);
        }
    } catch (error) {
        console.error('Error loading wallet:', error);
    }
}

async function setWallet() {
    showInterstitialIfNeeded();
    var userId = tgUser ? tgUser.id : '0';
    try {
        var response = await fetch(API_BASE + '/api/get_wallet?telegram_id=' + userId);
        var data = await response.json();
        if (data.success && data.wallet_address) {
            var withdrawAddress = document.getElementById('withdrawAddress');
            if (withdrawAddress) {
                withdrawAddress.value = data.wallet_address;
                safePopup({title:'✅ Wallet Loaded!', message:'Polygon wallet loaded: ' + data.wallet_address.slice(0,6) + '...' + data.wallet_address.slice(-4), buttons:[{type:'ok'}]});
            }
        } else {
            safePopup({title:'❌ No Wallet Found', message:'Please save a Polygon wallet address first.', buttons:[{type:'ok'}]});
        }
    } catch (error) {
        console.error('Error loading wallet:', error);
        safePopup({title:'❌ Error', message:'Failed to load wallet.', buttons:[{type:'ok'}]});
    }
}

// ============================================
// INVESTMENT FUNCTIONS
// ============================================
function calculateReturn(amount, days) {
    const multipliers = {
        1: 1.02,
        7: 1.18,
        30: 1.80
    };
    const multiplier = multipliers[days] || 1.80;
    return amount * multiplier;
}

function getLockOptions() {
    return [
        { days: 1, returnPercent: 2 },
        { days: 7, returnPercent: 18 },
        { days: 30, returnPercent: 80 }
    ];
}

async function investFieldWithLock(fieldNumber) {
    showInterstitialIfNeeded();
    const userId = tgUser ? tgUser.id : '0';

    const amount = prompt('Enter amount to invest in Field #' + fieldNumber + ' (min $5, max $100):');
    if (!amount) return;

    const amountNum = parseFloat(amount.replace('$', '').trim());
    if (isNaN(amountNum) || amountNum < 5 || amountNum > 100) {
        safePopup({title:'❌ Invalid Amount', message:'Please enter between $5 and $100.', buttons:[{type:'ok'}]});
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
        message: 'Field #' + fieldNumber + '\n\n💰 Amount: $' + amountNum.toFixed(2) + '\n⏱️ Lock Period: ' + days + ' day' + (days > 1 ? 's' : '') + '\n📈 Expected Return: $' + expectedReturn.toFixed(2) + '\n✅ Profit: +$' + profit.toFixed(2) + '\n⛓️ Network: Polygon',
        buttons: [
            {id:'cancel', type:'cancel'},
            {id:'confirm', type:'ok', text:'✅ Confirm'}
        ]
    }, async function(buttonId) {
        if (buttonId === 'confirm') {
            try {
                const response = await fetch(API_BASE + '/api/invest_locked', {
                    method:'POST',
                    headers:{'Content-Type':'application/json'},
                    body:JSON.stringify({
                        telegram_id: userId,
                        field_number: fieldNumber,
                        amount: amountNum,
                        lock_period: days
                    })
                });
                const data = await response.json();
                if (data.success) {
                    safePopup({
                        title:'✅ Success!',
                        message:'Invested $' + amountNum.toFixed(2) + ' in Field #' + fieldNumber + ' on Polygon!\n🔒 Locked for ' + days + ' days.\n📈 Expected return: $' + expectedReturn.toFixed(2),
                        buttons:[{type:'ok'}]
                    });

                    if (window.watchRewardedAd) {
                        console.log("📢 Showing rewarded ad after investment...");
                        setTimeout(function() { window.watchRewardedAd(); }, 500);
                    }

                    if (window.showInterstitialAd) {
                        console.log("📢 Showing interstitial ad after investment (NO REWARD)...");
                        setTimeout(function() { window.showInterstitialAd(); }, 1000);
                    }

                    loadUserData();
                } else {
                    safePopup({title:'❌ Error', message:data.message || 'Investment failed.', buttons:[{type:'ok'}]});
                }
            } catch (error) {
                console.error('Error investing:', error);
                safePopup({title:'❌ Error', message:'Network error. Please try again.', buttons:[{type:'ok'}]});
            }
        }
    });
}

async function investField(fieldNumber) {
    await investFieldWithLock(fieldNumber);
}

// ============================================
// COPY FUNCTIONS
// ============================================
function copyAddress() {
    showInterstitialIfNeeded();
    var addressElement = document.getElementById('addressText');
    var address = addressElement ? addressElement.textContent.trim() : '';

    if (!address) {
        var displayElement = document.querySelector('.address');
        if (displayElement) {
            address = displayElement.textContent.trim();
        }
    }

    address = address.replace(/\s+/g, '').trim();

    if (address && address.startsWith('0x') && address.length === 42) {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(address).then(function() {
                safePopup({
                    title: '✅ Copied!',
                    message: 'Polygon address copied.',
                    buttons: [{type: 'ok'}]
                });
            }).catch(function() {
                var textArea = document.createElement('textarea');
                textArea.value = address;
                document.body.appendChild(textArea);
                textArea.select();
                document.execCommand('copy');
                document.body.removeChild(textArea);
                safePopup({
                    title: '✅ Copied!',
                    message: 'Polygon address copied.',
                    buttons: [{type: 'ok'}]
                });
            });
        } else {
            var textArea = document.createElement('textarea');
            textArea.value = address;
            document.body.appendChild(textArea);
            textArea.select();
            document.execCommand('copy');
            document.body.removeChild(textArea);
            safePopup({
                title: '✅ Copied!',
                message: 'Polygon address copied.',
                buttons: [{type: 'ok'}]
            });
        }
    } else {
        safePopup({
            title: '❌ Error',
            message: 'Invalid address. Please try again.',
            buttons: [{type: 'ok'}]
        });
    }
}

// ============================================
// DEPOSIT FUNCTIONS
// ============================================
async function checkDeposit() {
    var statusDiv = document.getElementById('depositStatus');
    if (statusDiv) {
        statusDiv.innerHTML = '🔍 Checking Polygon for deposits...';
        try {
            var userId = tgUser ? tgUser.id : '0';
            var response = await fetch(API_BASE + '/api/check_deposit?telegram_id=' + userId);
            var data = await response.json();
            if (data.success) {
                statusDiv.innerHTML = '✅ Deposit detected on Polygon! Balance updated.';
                loadUserData();
            } else {
                statusDiv.innerHTML = '⏳ No new deposits found on Polygon.';
            }
        } catch (error) {
            statusDiv.innerHTML = '❌ Error checking deposits.';
        }
    }
}

async function checkDepositWithAmount() {
    showInterstitialIfNeeded();
    const userId = tgUser?.id || '0';
    const amountInput = document.getElementById('depositAmount');
    const amount = amountInput?.value;

    if (!amount || parseFloat(amount) < 5) {
        safePopup({
            title: '⚠️ Invalid Amount',
            message: 'Please enter at least $5 USDT on Polygon.',
            buttons: [{type: 'ok'}]
        });
        return;
    }

    const statusDiv = document.getElementById('depositStatus');
    if (statusDiv) {
        statusDiv.innerHTML = '🔍 Checking Polygon for deposits...';
        statusDiv.className = 'deposit-status pending';
        statusDiv.style.display = 'block';
        try {
            const response = await fetch(`${API_BASE}/api/check_deposit_with_amount?telegram_id=${userId}&expected_amount=${parseFloat(amount)}`);
            const data = await response.json();
            if (data.success) {
                statusDiv.innerHTML = '✅ ' + data.message;
                statusDiv.className = 'deposit-status success';
                setTimeout(() => {
                    window.location.reload();
                }, 2000);
            } else {
                statusDiv.innerHTML = '⏳ ' + data.message;
                statusDiv.className = 'deposit-status pending';
            }
        } catch (error) {
            statusDiv.innerHTML = '❌ Error checking deposits on Polygon. Please try again.';
            statusDiv.className = 'deposit-status error';
        }
    }
}

// ============================================
// HISTORY FUNCTIONS
// ============================================
function filterHistory(type) {
    var activeButton = null;
    var buttons = document.querySelectorAll('.filter-btn');
    
    for (var i = 0; i < buttons.length; i++) {
        var btnText = buttons[i].textContent.toLowerCase();
        if (btnText === type || btnText.includes(type)) {
            activeButton = buttons[i];
            break;
        }
    }
    
    if (!activeButton && buttons.length > 0) {
        activeButton = buttons[0];
    }
    
    for (var i = 0; i < buttons.length; i++) {
        buttons[i].classList.remove('active');
    }
    if (activeButton) {
        activeButton.classList.add('active');
    }
    
    var historyList = document.getElementById('historyList');
    if (!historyList) return;
    
    historyList.innerHTML = '<p class="empty-state">Loading...</p>';
    var userId = tgUser ? tgUser.id : '0';

    var url1 = API_BASE + '/api/real_history?telegram_id=' + userId;
    var url2 = API_BASE + '/api/investments/' + userId;

    Promise.all([fetch(url1), fetch(url2)])
        .then(function(responses) { 
            return Promise.all(responses.map(function(r) { return r.json(); })); 
        })
        .then(function(data) {
            var allTransactions = [];

            if (data[0].transactions && data[0].transactions.length > 0) {
                allTransactions = allTransactions.concat(data[0].transactions);
            }

            if (data[1].transactions && data[1].transactions.length > 0) {
                data[1].transactions.forEach(function(tx) {
                    tx.type = 'investment';
                });
                allTransactions = allTransactions.concat(data[1].transactions);
            }

            if (allTransactions.length === 0) {
                historyList.innerHTML = '<p class="empty-state">No transactions found on Polygon.</p>';
                return;
            }

            if (type !== 'all') {
                allTransactions = allTransactions.filter(function(tx) { 
                    if (type === 'deposits') {
                        return tx.type === 'deposit' || tx.type === 'deposits';
                    }
                    if (type === 'withdrawals') {
                        return tx.type === 'withdraw' || tx.type === 'withdrawal' || tx.type === 'withdrawals';
                    }
                    if (type === 'earnings') {
                        return tx.type === 'earnings' || tx.type === 'earning' || tx.type === 'payout' || 
                               tx.type === 'referral_earnings' || tx.type === 'ad_earnings' || tx.type === 'tasks_earnings';
                    }
                    if (type === 'investments') {
                        return tx.type === 'investment' || tx.type === 'investments';
                    }
                    return tx.type === type; 
                });
            }

            if (allTransactions.length === 0) {
                var displayType = type;
                if (type === 'deposits') displayType = 'deposit';
                if (type === 'withdrawals') displayType = 'withdrawal';
                if (type === 'earnings') displayType = 'earning';
                if (type === 'investments') displayType = 'investment';
                historyList.innerHTML = '<p class="empty-state">No ' + displayType + ' transactions found on Polygon.</p>';
                return;
            }

            allTransactions.sort(function(a, b) { 
                return new Date(b.date) - new Date(a.date); 
            });

            renderHistory(allTransactions);
        })
        .catch(function(error) {
            console.error('Error loading history:', error);
            historyList.innerHTML = '<p class="empty-state">Error loading history. Please try again.</p>';
        });
}

function renderHistory(transactions) {
    var historyList = document.getElementById('historyList');
    if (!historyList) return;
    
    var html = '';
    for (var i = 0; i < transactions.length; i++) {
        var tx = transactions[i];
        var icon = tx.type === 'deposit' ? '📥' : 
                   tx.type === 'withdraw' ? '📤' : 
                   tx.type === 'investment' ? '🌱' : 
                   tx.type === 'referral_earnings' ? '🎁' : 
                   tx.type === 'ad_earnings' ? '📺' : 
                   tx.type === 'tasks_earnings' ? '✅' : '💰';
        var status = tx.status || 'completed';
        var date = tx.date;
        var displayText = tx.type.charAt(0).toUpperCase() + tx.type.slice(1);
        if (tx.type === 'referral_earnings') {
            displayText = 'Referral Bonus';
        }
        if (tx.type === 'ad_earnings') {
            displayText = 'Ad Earnings';
        }
        if (tx.type === 'tasks_earnings') {
            displayText = 'Tasks Earnings';
        }

        var amountDisplay = '$' + tx.amount.toFixed(3);
        if (tx.type === 'investment' && tx.field) {
            amountDisplay = '$' + tx.amount.toFixed(3) + ' (Field ' + tx.field + ')';
        }

        var statusBadge = '';
        if (tx.type === 'withdraw' && tx.status === 'pending') {
            statusBadge = ' ⏳';
        }

        html += '<div class="history-item">' +
            '<div class="history-icon">' + icon + '</div>' +
            '<div class="history-details">' +
                '<div class="history-type">' + displayText + ' 🟣 Polygon' + statusBadge + '</div>' +
                '<div class="history-date">' + date + '</div>' +
            '</div>' +
            '<div class="history-amount ' + status + '">' + amountDisplay + '</div>' +
        '</div>';
    }
    historyList.innerHTML = html;
}

// ============================================
// EVENT LISTENERS
// ============================================
function setupEventListeners() {
    var withdrawForm = document.getElementById('withdrawForm');
    if (withdrawForm) {
        withdrawForm.addEventListener('submit', function(e) {
            e.preventDefault();
            showInterstitialIfNeeded();
            var amountInput = document.getElementById('withdrawAmount');
            var addressInput = document.getElementById('withdrawAddress');
            var amount = amountInput ? amountInput.value : '';
            var address = addressInput ? addressInput.value : '';
            if (!amount || parseFloat(amount) < 2) {
                safePopup({title:'❌ Error', message:'Please enter at least $2 USDT for withdrawal on Polygon.', buttons:[{type:'ok'}]});
                return;
            }
            if (!address || !address.startsWith('0x')) {
                safePopup({title:'❌ Error', message:'Please enter a valid Polygon wallet address.', buttons:[{type:'ok'}]});
                return;
            }
            if (address.toLowerCase() === PROJECT_WALLET.toLowerCase()) {
                safePopup({title:'❌ Invalid Wallet', message:'Cannot withdraw to project wallet on Polygon.', buttons:[{type:'ok'}]});
                return;
            }
            var userId = tgUser ? tgUser.id : '0';
            var submitBtn = document.querySelector('.withdraw-btn');
            if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = '⏳ Processing...'; }
            fetch(API_BASE + '/api/withdraw', {
                method:'POST',
                headers:{'Content-Type':'application/json'},
                body:JSON.stringify({telegram_id:userId, amount:parseFloat(amount), address:address})
            })
                .then(function(response) { return response.json(); })
                .then(function(data) {
                    if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = '🌱 Request Withdrawal'; }
                    if (data.success) {
                        safePopup({title:'✅ Success!', message:data.message || 'Withdrawal submitted on Polygon!', buttons:[{type:'ok'}]});

                        if (window.watchRewardedAd) {
                            console.log("📢 Showing rewarded ad after withdrawal...");
                            setTimeout(function() { window.watchRewardedAd(); }, 500);
                        }

                        if (window.showInterstitialAd) {
                            console.log("📢 Showing interstitial ad after withdrawal (NO REWARD)...");
                            setTimeout(function() { window.showInterstitialAd(); }, 1000);
                        }

                        if (amountInput) amountInput.value = '';
                    } else {
                        safePopup({title:'❌ Error', message:data.message || 'Withdrawal failed.', buttons:[{type:'ok'}]});
                    }
                })
                .catch(function(error) {
                    console.error('Error:', error);
                    if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = '🌱 Request Withdrawal'; }
                    safePopup({title:'❌ Error', message:'Network error. Please try again.', buttons:[{type:'ok'}]});
                });
        });
    }
}

// ============================================
// AD REWARD FUNCTIONS
// ============================================
async function canWatchAd() {
    return true;
}

async function creditAdReward() {
    const userId = tgUser ? tgUser.id : '0';
    try {
        const response = await fetch(API_BASE + '/api/credit_ad_reward', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ telegram_id: userId })
        });
        const data = await response.json();
        return data.success || false;
    } catch (error) {
        console.error('Error crediting ad reward:', error);
        return false;
    }
}

async function watchRewardedAd() {
    console.log('📢 watchRewardedAd called');

    if (!window.showRewardedAd) {
        console.log('📢 Rewarded ad not available');
        safePopup({
            title: '❌ Ad Not Available',
            message: 'No ads available right now. Please try again later.',
            buttons: [{type: 'ok'}]
        });
        return false;
    }

    try {
        const result = await window.showRewardedAd();
        console.log('📢 Ad result:', result);

        if (result.done && !result.error && result.state === 'destroy') {
            const credited = await creditAdReward();
            if (credited) {
                safePopup({
                    title: '🎁 Bonus Earned!',
                    message: 'You earned $0.001 USDT for watching the ad!',
                    buttons: [{type: 'ok'}]
                });
                loadUserData();
                loadAdStats();
                loadActiveReferrals();
                loadTasks();
                return true;
            }
        }
        safePopup({
            title: '❌ Ad Not Available',
            message: 'No ads available right now. Please try again later.',
            buttons: [{type: 'ok'}]
        });
        return false;
    } catch (error) {
        console.error('Error watching ad:', error);
        safePopup({
            title: '❌ Ad Not Available',
            message: 'No ads available right now. Please try again later.',
            buttons: [{type: 'ok'}]
        });
        return false;
    }
}

async function loadAdStats() {
    const userId = tgUser ? tgUser.id : '0';
    try {
        const userResponse = await fetch(API_BASE + '/api/user?telegram_id=' + userId);
        const userData = await userResponse.json();

        const adEarningsEl = document.getElementById('adEarnings');
        if (adEarningsEl) {
            adEarningsEl.textContent = '$' + Number(userData.total_ad_earnings || 0).toFixed(3);
        }

        const adsTodayEl = document.getElementById('adsToday');
        if (adsTodayEl) {
            adsTodayEl.textContent = '♾️ Unlimited';
        }

        const watchBtn = document.getElementById('watchAdBtn');
        const statusEl = document.getElementById('adStatus');
        if (watchBtn) {
            watchBtn.disabled = false;
            watchBtn.style.opacity = '1';
            watchBtn.textContent = '▶️ Watch Ad & Earn $0.001';
            if (statusEl) {
                statusEl.style.display = 'none';
            }
        }
    } catch (error) {
        console.error('Error loading ad stats:', error);
    }
}

// ============================================
// REFERRAL UPGRADE FUNCTIONS
// ============================================
async function upgradeReferralTier(tier) {
    showInterstitialIfNeeded();
    const userId = tgUser ? tgUser.id : '0';

    if (!userId || userId === '0') {
        safePopup({
            title: '❌ Error',
            message: 'User not authenticated. Please restart the app.',
            buttons: [{type: 'ok'}]
        });
        return;
    }

    safePopupWithCallback({
        title: '📊 Upgrade Referral Tier',
        message: 'Are you sure you want to upgrade to ' + tier.toUpperCase() + ' tier?\n\nThis is a PERMANENT upgrade. No refunds.',
        buttons: [
            {id: 'cancel', type: 'cancel'},
            {id: 'confirm', type: 'ok', text: '✅ Upgrade'}
        ]
    }, async function(buttonId) {
        if (buttonId === 'confirm') {
            try {
                const response = await fetch(API_BASE + '/api/upgrade_tier', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        telegram_id: userId,
                        tier: tier
                    })
                });

                const data = await response.json();

                if (data.success) {
                    safePopup({
                        title: '✅ Upgrade Successful!',
                        message: data.message + '\n\nNew balance: $' + data.new_balance.toFixed(2),
                        buttons: [{type: 'ok'}]
                    });

                    setTimeout(function() {
                        loadUserData();
                    }, 1000);
                } else {
                    safePopup({
                        title: '❌ Error',
                        message: data.message || 'Upgrade failed.',
                        buttons: [{type: 'ok'}]
                    });
                }
            } catch (error) {
                console.error('Error upgrading tier:', error);
                safePopup({
                    title: '❌ Error',
                    message: 'Network error. Please try again.',
                    buttons: [{type: 'ok'}]
                });
            }
        }
    });
}

// ============================================
// NEW FEATURE FUNCTIONS
// ============================================

async function loadActiveReferrals() {
    const userId = tgUser ? tgUser.id : '0';
    try {
        const response = await fetch(`${API_BASE}/api/get_active_referrals/${userId}`);
        const data = await response.json();
        
        if (data.success) {
            const activeRefsEl = document.getElementById('activeReferralsCount');
            if (activeRefsEl) {
                activeRefsEl.textContent = data.active_count + ' / ' + data.total_referrals;
            }
            
            const listEl = document.getElementById('activeReferralList');
            if (listEl) {
                if (data.active_list && data.active_list.length > 0) {
                    let html = '<div style="font-size:12px;color:#8892b0;margin-bottom:6px;">👥 Active Referrals (eligible for 0.03 USDT bonus):</div>';
                    data.active_list.forEach(ref => {
                        const status = ref.has_invested ? '💰 Invested' : `📺 ${ref.ads_watched}/30 ads`;
                        html += `<div style="display:flex;justify-content:space-between;align-items:center;padding:6px 8px;background:rgba(0,255,135,0.03);border-radius:6px;margin-bottom:4px;border:1px solid rgba(0,255,135,0.05);">
                            <span style="font-size:13px;color:#ccd6f0;">👤 ${ref.username}</span>
                            <span style="font-size:11px;color:#00ff87;">✅ ${status}</span>
                            <span style="font-size:11px;color:#ffd93d;">+0.03 USDT</span>
                        </div>`;
                    });
                    listEl.innerHTML = html;
                    listEl.style.display = 'block';
                } else {
                    listEl.innerHTML = '<p style="color:#495670;font-size:13px;padding:8px 0;">No active referrals yet. Share your link!</p>';
                    listEl.style.display = 'block';
                }
            }
        }
    } catch (error) {
        console.error('Error loading active referrals:', error);
    }
}

async function claimWelcomeBonus() {
    const userId = tgUser ? tgUser.id : '0';
    
    safePopupWithCallback({
        title: '🎁 Welcome Bonus',
        message: 'Claim 0.1 USDT as a welcome bonus!\n\nRequirement: Invest at least once OR watch 30 ads.\n\nNo referral needed! 🎉',
        buttons: [
            {id: 'cancel', type: 'cancel'},
            {id: 'claim', type: 'ok', text: '🎁 Claim'}
        ]
    }, async function(buttonId) {
        if (buttonId === 'claim') {
            try {
                const response = await fetch(`${API_BASE}/api/claim_welcome_bonus`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ telegram_id: userId })
                });
                const data = await response.json();
                
                if (data.success) {
                    safePopup({
                        title: '🎉 Bonus Claimed!',
                        message: data.message + '\n\nNew balance: $' + data.new_balance.toFixed(2),
                        buttons: [{type: 'ok'}]
                    });
                    loadUserData();
                    loadActiveReferrals();
                    loadTasks();
                } else {
                    safePopup({
                        title: '❌ Error',
                        message: data.message || 'Failed to claim bonus.',
                        buttons: [{type: 'ok'}]
                    });
                }
            } catch (error) {
                console.error('Error claiming bonus:', error);
                safePopup({
                    title: '❌ Error',
                    message: 'Network error. Please try again.',
                    buttons: [{type: 'ok'}]
                });
            }
        }
    });
}

// ============================================
// DISABLE INTERSTITIAL ADS - HARDCODED $4
// ============================================
async function disableInterstitialAds() {
    const userId = tgUser ? tgUser.id : '0';
    
    safePopupWithCallback({
        title: '🔇 Disable Ads',
        message: 'Pay $4 USDT to reduce pop-up ads on button clicks.\n\n⚠️ Note: This may not disable all ads but will disable most of them.\n\nYou will still be able to watch rewarded ads for $0.001 USDT.',
        buttons: [
            {id: 'cancel', type: 'cancel'},
            {id: 'confirm', type: 'ok', text: '✅ Pay $4'}
        ]
    }, async function(buttonId) {
        if (buttonId === 'confirm') {
            try {
                const response = await fetch(`${API_BASE}/api/disable_interstitial_ads`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ telegram_id: userId })
                });
                const data = await response.json();
                
                if (data.success) {
                    safePopup({
                        title: '✅ Ads Reduced!',
                        message: data.message + '\n\nMost interstitial ads disabled!',
                        buttons: [{type: 'ok'}]
                    });
                    const disableBtn = document.getElementById('disableAdsBtn');
                    if (disableBtn) {
                        disableBtn.textContent = '✅ Ads Disabled';
                        disableBtn.disabled = true;
                        disableBtn.style.opacity = '0.5';
                    }
                    interstitialAdsDisabled = true;
                    loadUserData();
                } else {
                    safePopup({
                        title: '❌ Error',
                        message: data.message || 'Failed to disable ads.',
                        buttons: [{type: 'ok'}]
                    });
                }
            } catch (error) {
                console.error('Error disabling ads:', error);
                safePopup({
                    title: '❌ Error',
                    message: 'Network error. Please try again.',
                    buttons: [{type: 'ok'}]
                });
            }
        }
    });
}

// ============================================
// TASK SYSTEM - 44 VISIBLE TASKS (Task 45 Hidden)
// ============================================

async function loadTasks() {
    console.log('🔄 Loading tasks...');
    const userId = tgUser ? tgUser.id : '0';
    try {
        const response = await fetch(`${API_BASE}/api/tasks/${userId}`);
        const data = await response.json();
        console.log('📊 Tasks API response:', data);
        
        if (data.success) {
            console.log('✅ Tasks loaded:', data.tasks.length, 'tasks found');
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
                        safePopup({
                            title: '🎉 Tasks Completed!',
                            message: 'You completed:\n• ' + taskNames.join('\n• ') + '\n\nGo to Tasks to claim your rewards!',
                            buttons: [{type: 'ok'}]
                        });
                    }
                }
                
                const visibleTasks = data.tasks.filter(task => !task.claimed);
                console.log('📊 Visible tasks (not claimed):', visibleTasks.length);
                totalTasks = visibleTasks.length;
                
                const categories = {
                    'investments': { icon: '🌱', label: 'Investments' },
                    'ads': { icon: '📺', label: 'Watch Ads' },
                    'referrals': { icon: '👤', label: 'Referrals' },
                    'active_referrals': { icon: '🔥', label: 'Active Referrals' },
                    'milestones': { icon: '🏆', label: 'Milestones' }
                };
                
                const sortedTasks = visibleTasks.sort((a, b) => a.task_id - b.task_id);
                
                let currentCategory = '';
                for (const task of sortedTasks) {
                    const isCompleted = task.completed;
                    const isClaimed = task.claimed;
                    if (isCompleted && !isClaimed) completedCount++;
                    
                    if (task.category !== currentCategory) {
                        currentCategory = task.category;
                        const catInfo = categories[currentCategory] || { icon: '📌', label: currentCategory };
                        html += `
                            <div style="margin-top:16px;margin-bottom:8px;font-size:14px;font-weight:700;color:#8247E5;border-bottom:1px solid rgba(130,71,229,0.2);padding-bottom:4px;">
                                ${catInfo.icon} ${catInfo.label}
                            </div>
                        `;
                    }
                    
                    const userStats = data.user_stats || {};
                    let progressText = '';
                    let progressPercent = 0;
                    
                    const conditionValue = getTaskConditionValue(task.task_id);
                    const currentValue = getTaskCurrentValue(task.task_id, userStats);
                    
                    if (!isCompleted && conditionValue !== null && currentValue !== null) {
                        if (task.category === 'milestones') {
                            progressText = `${Number(currentValue).toFixed(3)}/${conditionValue}`;
                        } else {
                            progressText = `${Math.round(Number(currentValue))}/${conditionValue}`;
                        }
                        progressPercent = Math.min((Number(currentValue) / conditionValue) * 100, 100);
                    } else if (!isCompleted && conditionValue === null && currentValue !== null) {
                        const maxVal = 1;
                        progressText = `${Math.round(Number(currentValue))}/${maxVal}`;
                        progressPercent = Math.min((Number(currentValue) / maxVal) * 100, 100);
                    } else if (isCompleted) {
                        const displayMax = conditionValue || 1;
                        const displayCurrent = conditionValue || 1;
                        progressText = `${displayCurrent}/${displayMax}`;
                        progressPercent = 100;
                    }
                    
                    const statusBadge = isCompleted ? 
                        '🟡 Claim Now!' : 
                        (progressText ? `⏳ ${progressText}` : '⏳ Current Task Progress');
                    const statusColor = isCompleted ? 
                        '#ffd93d' : 
                        '#495670';
                    
                    const rewardDisplay = task.reward < 0.01 ? '0.00' : Number(task.reward).toFixed(3);
                    
                    html += `
                        <div style="background:rgba(0,0,0,0.3);border:1px solid ${isCompleted ? 'rgba(255,217,61,0.3)' : 'rgba(255,255,255,0.05)'};border-radius:10px;padding:12px 14px;margin-bottom:8px;">
                            <div style="display:flex;justify-content:space-between;align-items:center;">
                                <div style="display:flex;align-items:center;gap:10px;flex:1;">
                                    <div style="font-size:20px;">${task.icon || '📌'}</div>
                                    <div style="flex:1;">
                                        <div style="font-weight:600;font-size:14px;color:${isCompleted ? '#ffd93d' : '#ccd6f0'};">${task.title}</div>
                                        <div style="font-size:12px;color:#8892b0;">${task.description}</div>
                                        <div style="font-size:11px;color:#ffd93d;">💰 ${rewardDisplay} USDT</div>
                                        ${!isCompleted && progressText ? `
                                            <div style="width:100%;height:4px;background:rgba(255,255,255,0.05);border-radius:2px;margin-top:4px;overflow:hidden;">
                                                <div style="width:${progressPercent}%;height:100%;background:linear-gradient(90deg,#8247E5,#00ff87);border-radius:2px;transition:width 0.5s ease;"></div>
                                            </div>
                                        ` : ''}
                                    </div>
                                </div>
                                <div style="text-align:right;">
                                    <div style="font-size:11px;color:${statusColor};">${statusBadge}</div>
                                    ${isCompleted ? `<button onclick="claimTaskReward(${task.task_id})" style="margin-top:4px;padding:4px 10px;background:linear-gradient(135deg,#ffd93d,#f9a825);border:none;border-radius:4px;color:#0a0e17;font-weight:700;font-size:11px;cursor:pointer;">💰 Claim</button>` : ''}
                                </div>
                            </div>
                        </div>
                    `;
                }
                
                if (totalTasks === 0) {
                    html = `
                        <div style="text-align:center;padding:30px 20px;background:rgba(0,255,135,0.05);border-radius:12px;border:1px solid rgba(0,255,135,0.1);">
                            <div style="font-size:48px;margin-bottom:10px;">🎉</div>
                            <div style="font-size:18px;font-weight:700;color:#00ff87;">All Tasks Completed!</div>
                            <div style="font-size:13px;color:#8892b0;margin-top:4px;">You've completed all 44 tasks. Great job!</div>
                        </div>
                    `;
                }
                
                tasksEl.innerHTML = html;
                console.log('✅ Tasks rendered successfully');
                
                const progressEl = document.getElementById('taskProgress');
                if (progressEl) {
                    const total = data.stats.total_tasks || 44;
                    const done = data.stats.completed_tasks || 0;
                    progressEl.textContent = `${done}/${total} tasks completed`;
                    progressEl.style.color = done === total ? '#00ff87' : '#ccd6f0';
                }
            }
        }
    } catch (error) {
        console.error('❌ Error loading tasks:', error);
    }
}

function getTaskConditionValue(taskId) {
    const taskConditions = {
        1: 1, 2: 10, 3: 50, 4: 100, 5: 200, 6: 500, 7: 1000,
        8: 1, 9: 5, 10: 10, 11: 25, 12: 50, 13: 100, 14: 250, 15: 500, 16: 1000,
        17: 1, 18: 3, 19: 5, 20: 10, 21: 25, 22: 50, 23: 100, 24: 250, 25: 500, 26: 1000,
        27: 1, 28: 3, 29: 5, 30: 10, 31: 25, 32: 50, 33: 100, 34: 250, 35: 500, 36: 1000,
        37: 1, 38: 10, 39: 25, 40: 50, 41: 100, 42: 250, 43: 500, 44: 1000
    };
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
        8: Number(userStats.total_ads_watched) || 0,
        9: Number(userStats.total_ads_watched) || 0,
        10: Number(userStats.total_ads_watched) || 0,
        11: Number(userStats.total_ads_watched) || 0,
        12: Number(userStats.total_ads_watched) || 0,
        13: Number(userStats.total_ads_watched) || 0,
        14: Number(userStats.total_ads_watched) || 0,
        15: Number(userStats.total_ads_watched) || 0,
        16: Number(userStats.total_ads_watched) || 0,
        17: Number(userStats.total_referrals) || 0,
        18: Number(userStats.total_referrals) || 0,
        19: Number(userStats.total_referrals) || 0,
        20: Number(userStats.total_referrals) || 0,
        21: Number(userStats.total_referrals) || 0,
        22: Number(userStats.total_referrals) || 0,
        23: Number(userStats.total_referrals) || 0,
        24: Number(userStats.total_referrals) || 0,
        25: Number(userStats.total_referrals) || 0,
        26: Number(userStats.total_referrals) || 0,
        27: Number(userStats.total_active_referrals) || 0,
        28: Number(userStats.total_active_referrals) || 0,
        29: Number(userStats.total_active_referrals) || 0,
        30: Number(userStats.total_active_referrals) || 0,
        31: Number(userStats.total_active_referrals) || 0,
        32: Number(userStats.total_active_referrals) || 0,
        33: Number(userStats.total_active_referrals) || 0,
        34: Number(userStats.total_active_referrals) || 0,
        35: Number(userStats.total_active_referrals) || 0,
        36: Number(userStats.total_active_referrals) || 0,
        37: Number(userStats.total_earnings) || 0,
        38: Number(userStats.total_earnings) || 0,
        39: Number(userStats.total_earnings) || 0,
        40: Number(userStats.total_earnings) || 0,
        41: Number(userStats.total_earnings) || 0,
        42: Number(userStats.total_earnings) || 0,
        43: Number(userStats.total_earnings) || 0,
        44: Number(userStats.total_earnings) || 0
    };
    
    const value = taskCurrentValues[taskId];
    return typeof value === 'number' ? value : 0;
}

async function claimTaskReward(taskId) {
    const userId = tgUser ? tgUser.id : '0';
    
    if (window.claimingInProgress) {
        console.log('⏳ Claim already in progress...');
        return;
    }
    
    safePopupWithCallback({
        title: '💰 Claim Reward',
        message: 'Claim your reward for completing this task?',
        buttons: [
            {id: 'cancel', type: 'cancel'},
            {id: 'confirm', type: 'ok', text: '💰 Claim'}
        ]
    }, async function(buttonId) {
        if (buttonId === 'confirm') {
            window.claimingInProgress = true;
            try {
                const response = await fetch(`${API_BASE}/api/claim_task_reward`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        telegram_id: userId,
                        task_id: taskId
                    })
                });
                
                const data = await response.json();
                console.log('📡 Claim response:', data);
                
                if (data.success === false && data.message === "Task not found") {
                    safePopup({
                        title: '✅ Already Claimed!',
                        message: 'This task was already claimed.',
                        buttons: [{type: 'ok'}]
                    });
                    loadTasks();
                    loadUserData();
                    window.claimingInProgress = false;
                    return;
                }
                
                if (data.success) {
                    const reward = parseFloat(data.message.match(/\d+\.?\d*/)?.[0] || '0');
                    const rewardDisplay = reward < 0.01 ? '0.00' : reward.toFixed(3);
                    
                    safePopup({
                        title: '🎉 Reward Claimed!',
                        message: 'Claimed $' + rewardDisplay + ' USDT!\n\nNew balance: $' + data.new_balance.toFixed(2),
                        buttons: [{type: 'ok'}]
                    });
                    loadTasks();
                    loadUserData();
                } else {
                    safePopup({
                        title: '❌ Error',
                        message: data.message || 'Failed to claim reward.',
                        buttons: [{type: 'ok'}]
                    });
                }
            } catch (error) {
                console.error('❌ Error claiming reward:', error);
                safePopup({
                    title: 'ℹ️ Check Your Balance',
                    message: 'Please refresh the app to see if your reward was credited.',
                    buttons: [{type: 'ok'}]
                });
                loadTasks();
                loadUserData();
            } finally {
                window.claimingInProgress = false;
            }
        }
    });
}

// ============================================
// EXPOSE FUNCTIONS
// ============================================
window.navigateTo = navigateTo;
window.goBack = goBack;
window.refreshData = refreshData;
window.copyAddress = copyAddress;
window.copyReferral = copyReferral;
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
window.claimWelcomeBonus = claimWelcomeBonus;
window.disableInterstitialAds = disableInterstitialAds;
window.loadTasks = loadTasks;
window.claimTaskReward = claimTaskReward;

console.log('✅ PlantUSDT app loaded successfully!');
console.log('📢 Welcome bonus: 0.1 USDT for ANY active user (no referral needed)');
console.log('📢 Task management system active with 44 visible tasks (Task 45 hidden)');
console.log('📢 All amounts displayed with 3 decimal places');
console.log('🔇 Interstitial ads disabled:', interstitialAdsDisabled);
