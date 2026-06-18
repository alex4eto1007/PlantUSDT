// PlantUSDT Mini App - JavaScript

let tg = window.Telegram.WebApp;
let tgUser = tg.initDataUnsafe?.user;
const PROJECT_WALLET = '0x6b2672E8b8A3D610AD3C148C70627f3b79D5cF76';

document.addEventListener('DOMContentLoaded', function() {
    tg.ready();
    tg.expand();
    loadUserData();
    loadSavedWallet();
    setupEventListeners();
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
        const userId = tgUser?.id || '0';
        const response = await fetch(`/api/user?telegram_id=${userId}`);
        const data = await response.json();
        if (data.success) {
            updateUI(data);
            updateFields(data);
            updateReferral(data);
        }
    } catch (error) {
        console.error('Error loading user data:', error);
    }
}

function updateUI(data) {
    const balanceEl = document.getElementById('balance');
    if (balanceEl) {
        balanceEl.textContent = `$${data.balance?.toFixed(2) || '0.00'}`;
    }
    
    // Update total earnings - SUM of investment + referral
    const totalEarningsEl = document.getElementById('totalEarnings');
    if (totalEarningsEl) {
        totalEarningsEl.textContent = `$${(data.total_earnings || 0).toFixed(2)}`;
    }
    
    // Update investment earnings
    const investmentEarningsEl = document.getElementById('investmentEarnings');
    if (investmentEarningsEl) {
        investmentEarningsEl.textContent = `$${(data.investment_earnings || 0).toFixed(2)}`;
    }
    
    // Update referral earnings
    const referralEarningsDisplayEl = document.getElementById('referralEarningsDisplay');
    if (referralEarningsDisplayEl) {
        referralEarningsDisplayEl.textContent = `$${(data.referral_earned || 0).toFixed(2)}`;
    }
}

function updateFields(data) {
    const fields = data.fields || [];
    for (let i = 1; i <= 3; i++) {
        const field = fields.find(f => f.field_number === i);
        const statusEl = document.getElementById(`field${i}Status`);
        const amountEl = document.getElementById(`field${i}Amount`);
        const daysEl = document.getElementById(`field${i}Days`);
        const earnedEl = document.getElementById(`field${i}Earned`);
        const progressEl = document.getElementById(`field${i}Progress`);
        const cardEl = document.getElementById(`field${i}`);
        const btnEl = cardEl?.querySelector('.action-btn');
        if (field) {
            const progress = field.paid_out / field.total_return * 100;
            const days = Math.floor((Date.now() - new Date(field.start_date).getTime()) / (1000 * 60 * 60 * 24)) + 1;
            statusEl.textContent = '🟢 Active';
            statusEl.className = 'field-status active';
            amountEl.textContent = `$${field.amount.toFixed(2)}`;
            daysEl.textContent = `${Math.min(days, 30)}/30`;
            earnedEl.textContent = `$${field.paid_out.toFixed(2)}`;
            progressEl.style.width = `${Math.min(progress, 100)}%`;
            cardEl.className = 'field-card active';
            btnEl.textContent = '🌱 Active';
            btnEl.disabled = true;
            btnEl.style.opacity = '0.5';
            btnEl.style.cursor = 'not-allowed';
        } else {
            statusEl.textContent = '✅ Available';
            statusEl.className = 'field-status available';
            amountEl.textContent = '$0.00';
            daysEl.textContent = '0/30';
            earnedEl.textContent = '$0.00';
            progressEl.style.width = '0%';
            cardEl.className = 'field-card';
            btnEl.textContent = '🌱 Plant Now';
            btnEl.disabled = false;
            btnEl.style.opacity = '1';
            btnEl.style.cursor = 'pointer';
        }
    }
}

async function updateReferral(data) {
    const referralLink = document.getElementById('referralLinkText');
    const referralCount = document.getElementById('referralCount');
    const referralEarned = document.getElementById('referralEarned');
    const walletText = document.getElementById('walletText');
    const isConnected = walletText?.textContent.includes('Connected');
    
    if (referralLink) {
        if (isConnected) {
            const userId = tgUser?.id || '0';
            try {
                const response = await fetch(`/api/get_referral_code?telegram_id=${userId}&t=${Date.now()}`);
                const result = await response.json();
                if (result.success && result.referral_code) {
                    referralLink.textContent = `https://t.me/PlantUSDT_bot?start=${result.referral_code}`;
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
    if (referralCount) {
        referralCount.textContent = data.referrals || 0;
    }
    if (referralEarned) {
        referralEarned.textContent = `$${(data.referral_earned || 0).toFixed(2)}`;
    }
}

async function saveWallet() {
    const userId = tgUser?.id || '0';
    const walletInput = document.getElementById('walletInput');
    const walletAddress = walletInput?.value.trim();
    if (!walletAddress) {
        tg.showPopup({title:'❌ Error', message:'Please enter a wallet address.', buttons:[{type:'ok'}]});
        return;
    }
    if (!walletAddress.startsWith('0x') || walletAddress.length !== 42) {
        tg.showPopup({title:'❌ Invalid Address', message:'Please enter a valid BSC wallet address.', buttons:[{type:'ok'}]});
        return;
    }
    if (walletAddress.toLowerCase() === PROJECT_WALLET.toLowerCase()) {
        tg.showPopup({title:'❌ Invalid Wallet', message:'This is the project wallet. Please enter your own.', buttons:[{type:'ok'}]});
        return;
    }
    try {
        const response = await fetch('/api/save_wallet', {
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body:JSON.stringify({telegram_id:userId, wallet_address:walletAddress})
        });
        const data = await response.json();
        if (data.success) {
            tg.showPopup({title:'✅ Wallet Saved!', message:'Wallet saved: ' + walletAddress.slice(0,6) + '...' + walletAddress.slice(-4), buttons:[{type:'ok'}]});
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
    const statusText = document.getElementById('walletText');
    const addressDisplay = document.getElementById('walletAddressDisplay');
    const walletInput = document.getElementById('walletInput');
    const saveBtn = document.getElementById('saveWalletBtn');
    const disconnectBtn = document.getElementById('disconnectWalletBtn');
    if (statusText) {
        statusText.textContent = '✅ Wallet Connected';
        statusText.className = 'connected';
    }
    if (addressDisplay) {
        addressDisplay.textContent = '📍 ' + address;
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
    const statusText = document.getElementById('walletText');
    const addressDisplay = document.getElementById('walletAddressDisplay');
    const walletInput = document.getElementById('walletInput');
    const saveBtn = document.getElementById('saveWalletBtn');
    const disconnectBtn = document.getElementById('disconnectWalletBtn');
    if (statusText) {
        statusText.textContent = 'Wallet not connected';
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
    const userId = tgUser?.id || '0';
    tg.showPopup({
        title:'🔓 Disconnect Wallet',
        message:'Are you sure you want to disconnect your wallet?',
        buttons:[
            {id:'cancel', type:'cancel'},
            {id:'confirm', type:'ok', text:'Disconnect'}
        ]
    }, async function(buttonId) {
        if (buttonId === 'confirm') {
            try {
                const response = await fetch('/api/save_wallet', {
                    method:'POST',
                    headers:{'Content-Type':'application/json'},
                    body:JSON.stringify({telegram_id:userId, wallet_address:''})
                });
                const data = await response.json();
                if (data.success) {
                    resetWalletUI();
                    tg.showPopup({title:'✅ Disconnected', message:'Wallet disconnected.', buttons:[{type:'ok'}]});
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
    const userId = tgUser?.id || '0';
    try {
        const response = await fetch(`/api/get_wallet?telegram_id=${userId}`);
        const data = await response.json();
        if (data.success && data.wallet_address) {
            updateWalletUI(data.wallet_address);
        }
    } catch (error) {
        console.error('Error loading wallet:', error);
    }
}

async function setWallet() {
    const userId = tgUser?.id || '0';
    try {
        const response = await fetch(`/api/get_wallet?telegram_id=${userId}`);
        const data = await response.json();
        if (data.success && data.wallet_address) {
            const withdrawAddress = document.getElementById('withdrawAddress');
            if (withdrawAddress) {
                withdrawAddress.value = data.wallet_address;
                tg.showPopup({title:'✅ Wallet Loaded!', message:'Wallet loaded: ' + data.wallet_address.slice(0,6) + '...' + data.wallet_address.slice(-4), buttons:[{type:'ok'}]});
            }
        } else {
            tg.showPopup({title:'❌ No Wallet Found', message:'Please save a wallet address first.', buttons:[{type:'ok'}]});
        }
    } catch (error) {
        console.error('Error loading wallet:', error);
        tg.showPopup({title:'❌ Error', message:'Failed to load wallet.', buttons:[{type:'ok'}]});
    }
}

async function investField(fieldNumber) {
    const userId = tgUser?.id || '0';
    const amount = prompt('Enter amount to invest in Field #' + fieldNumber + ' (min $5, max $100):');
    if (!amount) return;
    
    // Remove $ symbol and any spaces
    let cleanAmount = amount.replace('$', '').trim();
    const amountNum = parseFloat(cleanAmount);
    
    if (isNaN(amountNum) || amountNum < 5 || amountNum > 100) {
        tg.showPopup({title:'❌ Invalid Amount', message:'Please enter between $5 and $100.', buttons:[{type:'ok'}]});
        return;
    }
    try {
        const response = await fetch('/api/invest', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({telegram_id:userId, field_number:fieldNumber, amount:amountNum})});
        const data = await response.json();
        if (data.success) {
            tg.showPopup({title:'✅ Success!', message:'$' + amountNum + ' invested in Field #' + fieldNumber + '!', buttons:[{type:'ok'}]});
            loadUserData();
        } else {
            tg.showPopup({title:'❌ Error', message:data.message || 'Investment failed.', buttons:[{type:'ok'}]});
        }
    } catch (error) { console.error('Error investing:', error); }
}

async function copyReferral() {
    const walletText = document.getElementById('walletText');
    const isConnected = walletText?.textContent.includes('Connected');
    if (!isConnected) {
        tg.showPopup({
            title: '⚠️ Wallet Required',
            message: 'You must save your wallet address first to get your referral link!\n\nPlease go to the main page and save your wallet address.',
            buttons: [{type: 'ok'}]
        });
        return;
    }
    const userId = tgUser?.id || '0';
    try {
        const response = await fetch(`/api/get_referral_code?telegram_id=${userId}&t=${Date.now()}`);
        const data = await response.json();
        if (data.success && data.referral_code) {
            const link = `https://t.me/PlantUSDT_bot?start=${data.referral_code}`;
            navigator.clipboard.writeText(link).then(() => {
                tg.showPopup({title:'✅ Copied!', message:'Referral link copied! Share it with your friends.', buttons:[{type:'ok'}]});
            }).catch(() => {
                tg.showPopup({title:'📋 Referral Link', message:link, buttons:[{type:'ok'}]});
            });
        } else {
            tg.showPopup({title:'❌ Error', message:'Could not get referral code.', buttons:[{type:'ok'}]});
        }
    } catch (error) {
        console.error('Error getting referral code:', error);
        tg.showPopup({title:'❌ Error', message:'Failed to get referral link. Please try again.', buttons:[{type:'ok'}]});
    }
}

function copyAddress() {
    const address = document.getElementById('addressText')?.textContent || '';
    if (address) {
        navigator.clipboard.writeText(address).then(() => {
            tg.showPopup({title:'✅ Copied!', message:'Wallet address copied.', buttons:[{type:'ok'}]});
        });
    }
}

async function checkDeposit() {
    const statusDiv = document.getElementById('depositStatus');
    if (statusDiv) {
        statusDiv.innerHTML = '🔍 Checking for deposits...';
        try {
            const userId = tgUser?.id || '0';
            const response = await fetch(`/api/check_deposit?telegram_id=${userId}`);
            const data = await response.json();
            if (data.success) {
                statusDiv.innerHTML = '✅ Deposit detected! Balance updated.';
                loadUserData();
            } else {
                statusDiv.innerHTML = '⏳ No new deposits found. Please wait 5-15 minutes.';
            }
        } catch (error) {
            statusDiv.innerHTML = '❌ Error checking deposits. Please try again.';
        }
    }
}

function filterHistory(type) {
    document.querySelectorAll('.filter-btn').forEach(btn => { btn.classList.remove('active'); });
    event.target.classList.add('active');
    const historyList = document.getElementById('historyList');
    historyList.innerHTML = '<p class="empty-state">Loading...</p>';
    const userId = tgUser?.id || '0';
    fetch(`/api/real_history?telegram_id=${userId}`)
        .then(response => response.json())
        .then(data => {
            if (data.transactions && data.transactions.length > 0) {
                let filtered = data.transactions;
                if (type !== 'all') {
                    filtered = data.transactions.filter(tx => tx.type === type);
                }
                renderHistory(filtered);
            } else {
                historyList.innerHTML = '<p class="empty-state">No transactions found.</p>';
            }
        })
        .catch(error => {
            historyList.innerHTML = '<p class="empty-state">Error loading history.</p>';
            console.error('Error:', error);
        });
}

function renderHistory(transactions) {
    const historyList = document.getElementById('historyList');
    let html = '';
    transactions.forEach(tx => {
        const icon = tx.type === 'deposit' ? '📥' : tx.type === 'withdraw' ? '📤' : '💰';
        const status = tx.status || 'completed';
        const date = new Date(tx.date).toLocaleDateString();
        html += '<div class="history-item"><div class="history-icon">' + icon + '</div><div class="history-details"><div class="history-type">' + tx.type.charAt(0).toUpperCase() + tx.type.slice(1) + '</div><div class="history-date">' + date + '</div></div><div class="history-amount ' + status + '">$' + tx.amount.toFixed(2) + '</div></div>';
    });
    historyList.innerHTML = html;
}

function setupEventListeners() {
    const withdrawForm = document.getElementById('withdrawForm');
    if (withdrawForm) {
        withdrawForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const amountInput = document.getElementById('withdrawAmount');
            const addressInput = document.getElementById('withdrawAddress');
            const amount = amountInput?.value;
            const address = addressInput?.value;
            if (!amount || parseFloat(amount) < 2) {
                tg.showPopup({title:'❌ Error', message:'Please enter at least $2 USDT.', buttons:[{type:'ok'}]});
                return;
            }
            if (!address || !address.startsWith('0x')) {
                tg.showPopup({title:'❌ Error', message:'Please enter a valid BSC wallet address.', buttons:[{type:'ok'}]});
                return;
            }
            if (address.toLowerCase() === PROJECT_WALLET.toLowerCase()) {
                tg.showPopup({title:'❌ Invalid Wallet', message:'Cannot withdraw to project wallet.', buttons:[{type:'ok'}]});
                return;
            }
            const userId = tgUser?.id || '0';
            const submitBtn = document.querySelector('.withdraw-btn');
            if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = '⏳ Processing...'; }
            fetch('/api/withdraw', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({telegram_id:userId, amount:parseFloat(amount), address:address})})
                .then(response => response.json())
                .then(data => {
                    if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = '🌱 Request Withdrawal'; }
                    if (data.success) {
                        tg.showPopup({title:'✅ Success!', message:data.message || 'Withdrawal submitted!', buttons:[{type:'ok'}]});
                        loadUserData();
                        if (amountInput) amountInput.value = '';
                    } else {
                        tg.showPopup({title:'❌ Error', message:data.message || 'Withdrawal failed.', buttons:[{type:'ok'}]});
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = '🌱 Request Withdrawal'; }
                    tg.showPopup({title:'❌ Error', message:'Network error. Please try again.', buttons:[{type:'ok'}]});
                });
        });
    }
}

window.navigateTo = navigateTo;
window.goBack = goBack;
window.copyAddress = copyAddress;
window.copyReferral = copyReferral;
window.checkDeposit = checkDeposit;
window.investField = investField;
window.filterHistory = filterHistory;
window.saveWallet = saveWallet;
window.disconnectWallet = disconnectWallet;
window.setWallet = setWallet;
