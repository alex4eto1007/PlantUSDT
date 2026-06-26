// PlantUSDT Mini App - JavaScript (Polygon Network)

let tg = window.Telegram.WebApp;
let tgUser = tg.initDataUnsafe ? tg.initDataUnsafe.user : null;
const PROJECT_WALLET = '0x6b2672E8b8A3D610AD3C148C70627f3b79D5cF76';
const API_BASE = 'https://plantusdt.ddns.net';
const NETWORK = 'Polygon';
const USDT_CONTRACT = '0xc2132D05D31c914a87C6611C10748AEb04B58e8F';
let timerInterval = null;

document.addEventListener('DOMContentLoaded', function() {
    tg.ready();
    tg.expand();
    loadUserData();
    loadSavedWallet();
    setupEventListeners();
    startCountdownTimer();
});

function navigateTo(page) {
    const pages = {
        'dashboard': 'dashboard.html',
        'deposit': 'deposit.html',
        'withdraw': 'withdraw.html',
        'history': 'history.html',
        'index': 'index.html'
    };
    if (pages[page]) window.location.href = pages[page];
}

function goBack() { window.history.back(); }

async function loadUserData() {
    try {
        const userId = tgUser ? tgUser.id : '0';
        const response = await fetch(`${API_BASE}/api/user?telegram_id=${userId}`);
        const data = await response.json();
        if (data.success) {
            updateUI(data);
            updateFields(data);
            updateReferral(data);
            updateDashboardUI(data);
            await updateReferralStats(userId);
        }
    } catch (error) {
        console.error('Error loading user data:', error);
    }
}

function refreshData() {
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
    }, 300);
}

async function updateReferralStats(userId) {
    try {
        const response = await fetch(`${API_BASE}/api/referral_stats/${userId}`);
        const data = await response.json();
        if (data.success) {
            document.getElementById('referralCount').textContent = data.total_referrals || 0;
            document.getElementById('referralEarned').textContent = '$' + (data.total_earnings || 0).toFixed(2);
            document.getElementById('level1Count').textContent = data.level1_count || 0;
            document.getElementById('level1Earnings').textContent = '$' + (data.level1_earnings || 0).toFixed(2);
            
            var level2Section = document.getElementById('level2Section');
            if (level2Section) level2Section.style.display = 'none';
        }
    } catch (error) {
        console.error('Error loading referral stats:', error);
    }
}

function updateUI(data) {
    var balanceEl = document.getElementById('balance');
    if (balanceEl) {
        balanceEl.textContent = '$' + (data.balance || 0).toFixed(2);
    }
    
    var totalEarningsEl = document.getElementById('totalEarnings');
    if (totalEarningsEl) {
        totalEarningsEl.textContent = '$' + (data.total_earnings || 0).toFixed(2);
    }
    
    var investmentEarningsEl = document.getElementById('investmentEarnings');
    if (investmentEarningsEl) {
        investmentEarningsEl.textContent = '$' + (data.investment_earnings || 0).toFixed(2);
    }
    
    var referralEarningsDisplayEl = document.getElementById('referralEarningsDisplay');
    if (referralEarningsDisplayEl) {
        referralEarningsDisplayEl.textContent = '$' + (data.referral_earned || 0).toFixed(2);
    }
}

function updateDashboardUI(data) {
    var dashBalance = document.getElementById('dashBalance');
    var dashInvested = document.getElementById('dashInvested');
    var dashEarned = document.getElementById('dashEarned');
    var dashDeposited = document.getElementById('dashDeposited');
    var dashReferrals = document.getElementById('dashReferrals');

    if (dashBalance) dashBalance.textContent = '$' + (data.balance || 0).toFixed(2);
    if (dashInvested) dashInvested.textContent = '$' + (data.total_invested || 0).toFixed(2);
    if (dashEarned) dashEarned.textContent = '$' + (data.total_earnings || 0).toFixed(2);
    if (dashDeposited) dashDeposited.textContent = '$' + (data.total_deposited || 0).toFixed(2);
    if (dashReferrals) dashReferrals.textContent = data.referrals || 0;
}

function updateFields(data) {
    var fields = data.fields || [];
    window.fieldData = {};
    
    for (var i = 1; i <= 3; i++) {
        var field = fields.find(function(f) { return f.field_number === i; });
        var statusEl = document.getElementById('field' + i + 'Status');
        var amountEl = document.getElementById('field' + i + 'Amount');
        var daysEl = document.getElementById('field' + i + 'Days');
        var earnedEl = document.getElementById('field' + i + 'Earned');
        var progressEl = document.getElementById('field' + i + 'Progress');
        var cardEl = document.getElementById('field' + i);
        var btnEl = cardEl ? cardEl.querySelector('.action-btn') : null;
        var timerEl = document.getElementById('field' + i + 'Timer');
        
        if (field) {
            var lockPeriod = field.lock_period || 30;
            var isLocked = field.is_locked || false;
            var unlockDate = new Date(field.unlock_date);
            var now = new Date();
            var daysRemaining = Math.max(0, Math.ceil((unlockDate - now) / (1000 * 60 * 60 * 24)));
            
            statusEl.textContent = isLocked ? '🔒 Locked' : '🟢 Active';
            statusEl.className = isLocked ? 'field-status locked' : 'field-status active';
            amountEl.textContent = '$' + field.amount.toFixed(2);
            daysEl.textContent = isLocked ? daysRemaining + '/' + lockPeriod + ' days' : lockPeriod + '/' + lockPeriod + ' days';
            
            var displayEarned = isLocked ? field.expected_return || 0 : field.paid_out || 0;
            earnedEl.textContent = '$' + displayEarned.toFixed(2);
            
            var progress = isLocked ? ((lockPeriod - daysRemaining) / lockPeriod) * 100 : 100;
            progressEl.style.width = Math.min(progress, 100) + '%';
            cardEl.className = 'field-card active';
            btnEl.textContent = isLocked ? '🔒 Locked' : '🌱 Active';
            btnEl.disabled = true;
            btnEl.style.opacity = '0.5';
            btnEl.style.cursor = 'not-allowed';
            
            window.fieldData[i] = {
                unlock_date: field.unlock_date,
                is_locked: isLocked,
                lock_period: lockPeriod
            };
        } else {
            statusEl.textContent = '✅ Available';
            statusEl.className = 'field-status available';
            amountEl.textContent = '$0.00';
            daysEl.textContent = '0 days';
            earnedEl.textContent = '$0.00';
            progressEl.style.width = '0%';
            cardEl.className = 'field-card';
            btnEl.textContent = '🌱 Plant Now';
            btnEl.disabled = false;
            btnEl.style.opacity = '1';
            btnEl.style.cursor = 'pointer';
            window.fieldData[i] = null;
        }
    }
}

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

async function saveWallet() {
    var userId = tgUser ? tgUser.id : '0';
    var walletInput = document.getElementById('walletInput');
    var walletAddress = walletInput ? walletInput.value.trim() : '';
    if (!walletAddress) {
        tg.showPopup({title:'❌ Error', message:'Please enter a Polygon wallet address.', buttons:[{type:'ok'}]});
        return;
    }
    if (!walletAddress.startsWith('0x') || walletAddress.length !== 42) {
        tg.showPopup({title:'❌ Invalid Address', message:'Please enter a valid Polygon wallet address.', buttons:[{type:'ok'}]});
        return;
    }
    if (walletAddress.toLowerCase() === PROJECT_WALLET.toLowerCase()) {
        tg.showPopup({title:'❌ Invalid Wallet', message:'This is the project wallet on Polygon. Please enter your own.', buttons:[{type:'ok'}]});
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
            tg.showPopup({title:'✅ Wallet Saved!', message:'Polygon wallet saved: ' + walletAddress.slice(0,6) + '...' + walletAddress.slice(-4), buttons:[{type:'ok'}]});
            updateWalletUI(walletAddress);
            loadUserData();
        } else {
            tg.showPopup({title:'❌ Error', message:data.message || 'Failed to save wallet.', buttons:[{type:'ok'}]});
        }
    } catch (error) {
        console.error('Error saving wallet:', error);
        tg.showPopup({title:'❌ Error', message:'Failed to save wallet. Please try again.', buttons:[{type:'ok'}]});
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
    var userId = tgUser ? tgUser.id : '0';
    tg.showPopup({
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
                    tg.showPopup({title:'✅ Disconnected', message:'Polygon wallet disconnected.', buttons:[{type:'ok'}]});
                } else {
                    tg.showPopup({title:'❌ Error', message:'Failed to disconnect.', buttons:[{type:'ok'}]});
                }
            } catch (error) {
                console.error('Error disconnecting wallet:', error);
                tg.showPopup({title:'❌ Error', message:'Failed to disconnect. Please try again.', buttons:[{type:'ok'}]});
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
    var userId = tgUser ? tgUser.id : '0';
    try {
        var response = await fetch(API_BASE + '/api/get_wallet?telegram_id=' + userId);
        var data = await response.json();
        if (data.success && data.wallet_address) {
            var withdrawAddress = document.getElementById('withdrawAddress');
            if (withdrawAddress) {
                withdrawAddress.value = data.wallet_address;
                tg.showPopup({title:'✅ Wallet Loaded!', message:'Polygon wallet loaded: ' + data.wallet_address.slice(0,6) + '...' + data.wallet_address.slice(-4), buttons:[{type:'ok'}]});
            }
        } else {
            tg.showPopup({title:'❌ No Wallet Found', message:'Please save a Polygon wallet address first.', buttons:[{type:'ok'}]});
        }
    } catch (error) {
        console.error('Error loading wallet:', error);
        tg.showPopup({title:'❌ Error', message:'Failed to load wallet.', buttons:[{type:'ok'}]});
    }
}

// ============================================
// INVESTMENT FUNCTIONS - UPDATED PERCENTAGES
// ============================================

function calculateReturn(amount, days) {
    const multipliers = {
        1: 1.02,    // 2%
        7: 1.15,    // 15%
        30: 1.65    // 65%
    };
    const multiplier = multipliers[days] || 1.65;
    return amount * multiplier;
}

function getLockOptions() {
    return [
        { days: 1, returnPercent: 2 },
        { days: 7, returnPercent: 15 },
        { days: 30, returnPercent: 65 }
    ];
}

async function investFieldWithLock(fieldNumber) {
    const userId = tgUser ? tgUser.id : '0';
    
    const amount = prompt('Enter amount to invest in Field #' + fieldNumber + ' (min $5, max $100):');
    if (!amount) return;
    
    const amountNum = parseFloat(amount.replace('$', '').trim());
    if (isNaN(amountNum) || amountNum < 5 || amountNum > 100) {
        tg.showPopup({title:'❌ Invalid Amount', message:'Please enter between $5 and $100.', buttons:[{type:'ok'}]});
        return;
    }
    
    const options = getLockOptions();
    let message = '📊 Choose lock period:\n\n';
    options.forEach(opt => {
        const returnAmount = calculateReturn(amountNum, opt.days);
        const profit = returnAmount - amountNum;
        message += `• ${opt.days} day${opt.days > 1 ? 's' : ''}: +${opt.returnPercent}% → $${returnAmount.toFixed(2)} (+$${profit.toFixed(2)})\n`;
    });
    message += '\n\nEnter 1, 7, or 30:';
    
    const lockPeriod = prompt(message);
    if (!lockPeriod) return;
    
    const days = parseInt(lockPeriod);
    if (![1, 7, 30].includes(days)) {
        tg.showPopup({title:'❌ Invalid Option', message:'Please enter 1, 7, or 30.', buttons:[{type:'ok'}]});
        return;
    }
    
    const expectedReturn = calculateReturn(amountNum, days);
    const profit = expectedReturn - amountNum;
    
    tg.showPopup({
        title: '📊 Confirm Investment',
        message: `Field #${fieldNumber}\n\n💰 Amount: $${amountNum.toFixed(2)}\n⏱️ Lock Period: ${days} day${days > 1 ? 's' : ''}\n📈 Expected Return: $${expectedReturn.toFixed(2)}\n✅ Profit: +$${profit.toFixed(2)}\n⛓️ Network: Polygon`,
        buttons: [
            {id:'cancel', type:'cancel'},
            {id:'confirm', type:'ok', text:'✅ Confirm'}
        ]
    }, async function(buttonId) {
        if (buttonId === 'confirm') {
            try {
                const response = await fetch(`${API_BASE}/api/invest_locked`, {
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
                    tg.showPopup({
                        title:'✅ Success!',
                        message:`Invested $${amountNum.toFixed(2)} in Field #${fieldNumber} on Polygon!\n🔒 Locked for ${days} days.\n📈 Expected return: $${expectedReturn.toFixed(2)}`,
                        buttons:[{type:'ok'}]
                    });
                    
                    // 📢 Show rewarded ad after investment
                    if (window.watchRewardedAd) {
                        console.log("📢 Showing rewarded ad after investment...");
                        await window.watchRewardedAd();
                    }
                    
                    loadUserData();
                } else {
                    tg.showPopup({title:'❌ Error', message:data.message || 'Investment failed.', buttons:[{type:'ok'}]});
                }
            } catch (error) {
                console.error('Error investing:', error);
                tg.showPopup({title:'❌ Error', message:'Network error. Please try again.', buttons:[{type:'ok'}]});
            }
        }
    });
}

async function investField(fieldNumber) {
    await investFieldWithLock(fieldNumber);
}

// ============================================
// ADDRESS COPY AND REFERRAL
// ============================================

function copyAddress() {
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
                tg.showPopup({
                    title: '✅ Copied!',
                    message: 'Polygon address copied: ' + address.slice(0,6) + '...' + address.slice(-4),
                    buttons: [{type: 'ok'}]
                });
            }).catch(function() {
                var textArea = document.createElement('textarea');
                textArea.value = address;
                document.body.appendChild(textArea);
                textArea.select();
                document.execCommand('copy');
                document.body.removeChild(textArea);
                tg.showPopup({
                    title: '✅ Copied!',
                    message: 'Polygon address copied: ' + address.slice(0,6) + '...' + address.slice(-4),
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
            tg.showPopup({
                title: '✅ Copied!',
                message: 'Polygon address copied: ' + address.slice(0,6) + '...' + address.slice(-4),
                buttons: [{type: 'ok'}]
            });
        }
    } else {
        tg.showPopup({
            title: '❌ Error',
            message: 'Invalid address. Please try again.',
            buttons: [{type: 'ok'}]
        });
    }
}

async function copyReferral() {
    var walletText = document.getElementById('walletText');
    var isConnected = walletText ? walletText.textContent.includes('Connected') : false;
    if (!isConnected) {
        tg.showPopup({
            title: '⚠️ Wallet Required',
            message: 'You must save your Polygon wallet address first to get your referral link!',
            buttons: [{type: 'ok'}]
        });
        return;
    }
    var userId = tgUser ? tgUser.id : '0';
    try {
        var response = await fetch(API_BASE + '/api/get_referral_code?telegram_id=' + userId + '&t=' + Date.now());
        var data = await response.json();
        if (data.success && data.referral_code) {
            var link = 'https://t.me/PlantUSDT_bot?start=' + data.referral_code;
            navigator.clipboard.writeText(link).then(function() {
                tg.showPopup({title: '✅ Copied!', message: 'Referral link copied!', buttons: [{type: 'ok'}]});
            }).catch(function() {
                tg.showPopup({title: '📋 Referral Link', message: link, buttons: [{type: 'ok'}]});
            });
        } else {
            tg.showPopup({title: '❌ Error', message: 'Could not get referral code.', buttons: [{type: 'ok'}]});
        }
    } catch (error) {
        console.error('Error getting referral code:', error);
        tg.showPopup({title: '❌ Error', message: 'Failed to get referral link.', buttons: [{type: 'ok'}]});
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
    const userId = tgUser?.id || '0';
    const amountInput = document.getElementById('depositAmount');
    const amount = amountInput?.value;
    
    if (!amount || parseFloat(amount) < 5) {
        tg.showPopup({
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
                statusDiv.innerHTML = '✅ Deposit detected on Polygon! Balance updated.';
                statusDiv.className = 'deposit-status success';
                loadUserData();
            } else {
                statusDiv.innerHTML = '⏳ No new deposits found on Polygon. Please wait a few minutes and try again.';
                statusDiv.className = 'deposit-status pending';
            }
        } catch (error) {
            statusDiv.innerHTML = '❌ Error checking deposits on Polygon. Please try again.';
            statusDiv.className = 'deposit-status error';
        }
    }
}

// ============================================
// HISTORY FUNCTIONS - FIXED
// ============================================

function filterHistory(type) {
    var buttons = document.querySelectorAll('.filter-btn');
    for (var i = 0; i < buttons.length; i++) {
        buttons[i].classList.remove('active');
    }
    event.target.classList.add('active');
    var historyList = document.getElementById('historyList');
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
                        return tx.type === 'earnings' || tx.type === 'earning' || tx.type === 'payout' || tx.type === 'referral_earnings';
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
    var html = '';
    for (var i = 0; i < transactions.length; i++) {
        var tx = transactions[i];
        var icon = tx.type === 'deposit' ? '📥' : 
                   tx.type === 'withdraw' ? '📤' : 
                   tx.type === 'investment' ? '🌱' : 
                   tx.type === 'referral_earnings' ? '🎁' : '💰';
        var status = tx.status || 'completed';
        var date = tx.date;
        var displayText = tx.type.charAt(0).toUpperCase() + tx.type.slice(1);
        if (tx.type === 'referral_earnings') {
            displayText = 'Referral Bonus';
        }
        
        var amountDisplay = '$' + tx.amount.toFixed(2);
        if (tx.type === 'investment' && tx.field) {
            amountDisplay = '$' + tx.amount.toFixed(2) + ' (Field ' + tx.field + ')';
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
// TIMER FUNCTIONS
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
        
        if (!timerEl || !statusEl) continue;
        
        var fieldData = window.fieldData ? window.fieldData[i] : null;
        if (!fieldData || !fieldData.unlock_date) {
            timerEl.textContent = '⏳ Payout: --:--:-- UTC';
            timerEl.className = 'field-timer';
            continue;
        }
        
        var isLocked = fieldData.is_locked || false;
        
        if (!isLocked) {
            timerEl.textContent = '🟢 Unlocked! (UTC)';
            timerEl.className = 'field-timer ready';
            continue;
        }
        
        var unlockDate = new Date(fieldData.unlock_date + 'Z').getTime();
        var timeLeft = unlockDate - utcNow;
        
        if (timeLeft <= 0) {
            timerEl.textContent = '🟢 Unlocked! (UTC)';
            timerEl.className = 'field-timer ready';
        } else {
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
        }
    }
}

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
// EVENT LISTENERS
// ============================================

function setupEventListeners() {
    var withdrawForm = document.getElementById('withdrawForm');
    if (withdrawForm) {
        withdrawForm.addEventListener('submit', function(e) {
            e.preventDefault();
            var amountInput = document.getElementById('withdrawAmount');
            var addressInput = document.getElementById('withdrawAddress');
            var amount = amountInput ? amountInput.value : '';
            var address = addressInput ? addressInput.value : '';
            if (!amount || parseFloat(amount) < 2) {
                tg.showPopup({title:'❌ Error', message:'Please enter at least $2 USDT for withdrawal on Polygon.', buttons:[{type:'ok'}]});
                return;
            }
            if (!address || !address.startsWith('0x')) {
                tg.showPopup({title:'❌ Error', message:'Please enter a valid Polygon wallet address.', buttons:[{type:'ok'}]});
                return;
            }
            if (address.toLowerCase() === PROJECT_WALLET.toLowerCase()) {
                tg.showPopup({title:'❌ Invalid Wallet', message:'Cannot withdraw to project wallet on Polygon.', buttons:[{type:'ok'}]});
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
                        tg.showPopup({title:'✅ Success!', message:data.message || 'Withdrawal submitted on Polygon!', buttons:[{type:'ok'}]});
                        
                        // 📢 Show rewarded ad after withdrawal
                        if (window.watchRewardedAd) {
                            console.log("📢 Showing rewarded ad after withdrawal...");
                            window.watchRewardedAd().then(function() {
                                loadUserData();
                            });
                        } else {
                            loadUserData();
                        }
                        
                        if (amountInput) amountInput.value = '';
                    } else {
                        tg.showPopup({title:'❌ Error', message:data.message || 'Withdrawal failed.', buttons:[{type:'ok'}]});
                    }
                })
                .catch(function(error) {
                    console.error('Error:', error);
                    if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = '🌱 Request Withdrawal'; }
                    tg.showPopup({title:'❌ Error', message:'Network error. Please try again.', buttons:[{type:'ok'}]});
                });
        });
    }
}

// ============================================
// AD REWARD FUNCTIONS
// ============================================

/**
 * Check if user can watch ads today (100/day limit)
 */
async function canWatchAd() {
    const userId = tgUser ? tgUser.id : '0';
    try {
        const response = await fetch(`${API_BASE}/api/can_watch_ad?telegram_id=${userId}`);
        const data = await response.json();
        return data.can_watch || false;
    } catch (error) {
        console.error('Error checking ad limit:', error);
        return false;
    }
}

/**
 * Credit ad reward to user
 */
async function creditAdReward() {
    const userId = tgUser ? tgUser.id : '0';
    try {
        const response = await fetch(`${API_BASE}/api/credit_ad_reward`, {
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

/**
 * Show rewarded ad and credit bonus
 */
async function watchRewardedAd() {
    // Check daily limit
    const canWatch = await canWatchAd();
    if (!canWatch) {
        tg.showPopup({
            title: '⚠️ Daily Limit Reached',
            message: 'You have watched 100 ads today. Come back tomorrow!',
            buttons: [{type: 'ok'}]
        });
        return false;
    }

    // Check if ad function exists
    if (!window.showRewardedAd) {
        console.log('📢 Rewarded ad not available');
        return false;
    }

    // Show ad
    const result = await window.showRewardedAd();
    
    if (result.done && !result.error) {
        // Credit reward
        const credited = await creditAdReward();
        if (credited) {
            tg.showPopup({
                title: '🎁 Bonus Earned!',
                message: `You earned $${window.AD_REWARD || 0.002} USDT for watching the ad!`,
                buttons: [{type: 'ok'}]
            });
            loadUserData();
            return true;
        }
    }
    return false;
}

// Expose ad functions
window.watchRewardedAd = watchRewardedAd;
window.canWatchAd = canWatchAd;

// Expose functions globally
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
