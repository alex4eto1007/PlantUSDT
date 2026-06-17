// PlantUSDT Mini App - JavaScript

// Telegram WebApp
let tg = window.Telegram.WebApp;
let tgUser = tg.initDataUnsafe?.user;

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    tg.ready();
    tg.expand();
    
    // Load user data
    loadUserData();
    
    // Load saved wallet
    loadSavedWallet();
    
    // Set up event listeners
    setupEventListeners();
});

// Navigation
function navigateTo(page) {
    if (page === 'dashboard') {
        window.location.href = 'dashboard.html';
    } else if (page === 'deposit') {
        window.location.href = 'deposit.html';
    } else if (page === 'withdraw') {
        window.location.href = 'withdraw.html';
    } else if (page === 'history') {
        window.location.href = 'history.html';
    } else if (page === 'index') {
        window.location.href = 'index.html';
    }
}

function goBack() {
    window.history.back();
}

// Load user data from bot
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

// Update UI with user data
function updateUI(data) {
    const balanceEl = document.getElementById('balance');
    if (balanceEl) {
        balanceEl.textContent = `$${data.balance?.toFixed(2) || '0.00'}`;
    }
}

// Update fields
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

// Update referral
function updateReferral(data) {
    const referralLink = document.getElementById('referralLinkText');
    const referralCount = document.getElementById('referralCount');
    const referralEarned = document.getElementById('referralEarned');
    
    if (referralLink) {
        const userId = tgUser?.id || '0';
        referralLink.textContent = `https://t.me/PlantUSDT_bot?start=${userId}`;
    }
    if (referralCount) {
        referralCount.textContent = data.referrals || 0;
    }
    if (referralEarned) {
        referralEarned.textContent = `$${(data.referral_earned || 0).toFixed(2)}`;
    }
}

// ============================================
// SIMPLE WALLET SAVE FUNCTIONS
// ============================================

async function saveWallet() {
    const userId = tgUser?.id || '0';
    const walletInput = document.getElementById('walletInput');
    const walletAddress = walletInput?.value.trim();
    
    if (!walletAddress) {
        tg.showPopup({
            title: '❌ Error',
            message: 'Please enter a wallet address.',
            buttons: [{type: 'ok'}]
        });
        return;
    }
    
    // Basic validation
    if (!walletAddress.startsWith('0x') || walletAddress.length !== 42) {
        tg.showPopup({
            title: '❌ Invalid Address',
            message: 'Please enter a valid BSC wallet address (starts with 0x, 42 characters).',
            buttons: [{type: 'ok'}]
        });
        return;
    }
    
    try {
        const response = await fetch('/api/save_wallet', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                telegram_id: userId,
                wallet_address: walletAddress
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            tg.showPopup({
                title: '✅ Wallet Saved!',
                message: `Wallet address saved: ${walletAddress.slice(0, 6)}...${walletAddress.slice(-4)}`,
                buttons: [{type: 'ok'}]
            });
            updateWalletUI(walletAddress);
        } else {
            tg.showPopup({
                title: '❌ Error',
                message: data.message || 'Failed to save wallet.',
                buttons: [{type: 'ok'}]
            });
        }
    } catch (error) {
        console.error('Error saving wallet:', error);
        tg.showPopup({
            title: '❌ Error',
            message: 'Failed to save wallet. Please try again.',
            buttons: [{type: 'ok'}]
        });
    }
}

function updateWalletUI(address) {
    const statusText = document.getElementById('walletText');
    const addressDisplay = document.getElementById('walletAddressDisplay');
    const walletInput = document.getElementById('walletInput');
    const saveBtn = document.querySelector('.wallet-input-group .action-btn');
    
    if (statusText) {
        statusText.textContent = '✅ Wallet Connected';
        statusText.className = 'connected';
    }
    if (addressDisplay) {
        addressDisplay.textContent = `📍 ${address}`;
        addressDisplay.style.display = 'block';
    }
    if (walletInput) {
        walletInput.value = address;
        walletInput.disabled = true;
        walletInput.style.opacity = '0.6';
    }
    if (saveBtn) {
        saveBtn.textContent = '✅ Saved';
        saveBtn.disabled = true;
        saveBtn.style.opacity = '0.6';
        saveBtn.style.cursor = 'default';
    }
}

// Load saved wallet from server
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

// Invest in a field
async function investField(fieldNumber) {
    const userId = tgUser?.id || '0';
    
    const amount = prompt(`Enter amount to invest in Field #${fieldNumber} (min $5, max $100):`);
    
    if (!amount) return;
    
    const amountNum = parseFloat(amount);
    if (isNaN(amountNum) || amountNum < 5 || amountNum > 100) {
        tg.showPopup({
            title: '❌ Invalid Amount',
            message: 'Please enter between $5 and $100.',
            buttons: [{type: 'ok'}]
        });
        return;
    }
    
    try {
        const response = await fetch('/api/invest', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                telegram_id: userId,
                field_number: fieldNumber,
                amount: amountNum
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            tg.showPopup({
                title: '✅ Success!',
                message: `$${amountNum} invested in Field #${fieldNumber}!`,
                buttons: [{type: 'ok'}]
            });
            loadUserData();
        } else {
            tg.showPopup({
                title: '❌ Error',
                message: data.message || 'Investment failed.',
                buttons: [{type: 'ok'}]
            });
        }
    } catch (error) {
        console.error('Error investing:', error);
    }
}

// Copy referral link
function copyReferral() {
    const userId = tgUser?.id || '0';
    const link = `https://t.me/PlantUSDT_bot?start=${userId}`;
    
    navigator.clipboard.writeText(link).then(() => {
        tg.showPopup({
            title: '✅ Copied!',
            message: 'Referral link copied! Share it with your friends.',
            buttons: [{type: 'ok'}]
        });
    }).catch(() => {
        tg.showPopup({
            title: '📋 Referral Link',
            message: link,
            buttons: [{type: 'ok'}]
        });
    });
}

// Copy address
function copyAddress() {
    const address = document.getElementById('addressText')?.textContent || '';
    if (address) {
        navigator.clipboard.writeText(address).then(() => {
            tg.showPopup({
                title: '✅ Copied!',
                message: 'Wallet address copied to clipboard',
                buttons: [{type: 'ok'}]
            });
        });
    }
}

// Check deposit
async function checkDeposit() {
    const statusDiv = document.getElementById('depositStatus');
    if (statusDiv) {
        statusDiv.innerHTML = '🔍 Checking for deposits...';
        
        try {
            const userId = tgUser?.id || '0';
            const response = await fetch(`/api/check_deposit?telegram_id=${userId}`);
            const data = await response.json();
            
            if (data.success) {
                statusDiv.innerHTML = '✅ Deposit detected! Your balance has been updated.';
                loadUserData();
            } else {
                statusDiv.innerHTML = '⏳ No new deposits found. Please wait 5-15 minutes.';
            }
        } catch (error) {
            statusDiv.innerHTML = '❌ Error checking deposits. Please try again.';
        }
    }
}

// Filter history
function filterHistory(type) {
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    event.target.classList.add('active');
    
    const historyList = document.getElementById('historyList');
    historyList.innerHTML = '<p class="empty-state">Loading...</p>';
    
    const userId = tgUser?.id || '0';
    fetch(`/api/history?type=${type}&telegram_id=${userId}`)
        .then(response => response.json())
        .then(data => {
            if (data.transactions && data.transactions.length > 0) {
                renderHistory(data.transactions);
            } else {
                historyList.innerHTML = '<p class="empty-state">No transactions found.</p>';
            }
        })
        .catch(error => {
            historyList.innerHTML = '<p class="empty-state">Error loading history.</p>';
        });
}

// Render history items
function renderHistory(transactions) {
    const historyList = document.getElementById('historyList');
    let html = '';
    
    transactions.forEach(tx => {
        const type = tx.type || 'deposit';
        const icon = type === 'deposit' ? '📥' : type === 'withdraw' ? '📤' : '💰';
        const amount = tx.amount || 0;
        const status = tx.status || 'completed';
        const date = new Date(tx.date).toLocaleDateString();
        
        html += `
            <div class="history-item">
                <div class="history-icon">${icon}</div>
                <div class="history-details">
                    <div class="history-type">${type.charAt(0).toUpperCase() + type.slice(1)}</div>
                    <div class="history-date">${date}</div>
                </div>
                <div class="history-amount ${status}">$${amount.toFixed(2)}</div>
            </div>
        `;
    });
    
    historyList.innerHTML = html;
}

// Setup event listeners
function setupEventListeners() {
    const withdrawForm = document.getElementById('withdrawForm');
    if (withdrawForm) {
        withdrawForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const amount = document.getElementById('withdrawAmount')?.value;
            const address = document.getElementById('withdrawAddress')?.value;
            
            if (!amount || amount < 2) {
                tg.showPopup({
                    title: '❌ Error',
                    message: 'Please enter at least $2 USDT.',
                    buttons: [{type: 'ok'}]
                });
                return;
            }
            
            if (!address || !address.startsWith('0x')) {
                tg.showPopup({
                    title: '❌ Error',
                    message: 'Please enter a valid BSC wallet address.',
                    buttons: [{type: 'ok'}]
                });
                return;
            }
            
            const userId = tgUser?.id || '0';
            fetch('/api/withdraw', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    telegram_id: userId,
                    amount: parseFloat(amount),
                    address: address
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    tg.showPopup({
                        title: '✅ Success!',
                        message: 'Withdrawal request submitted successfully!',
                        buttons: [{type: 'ok'}]
                    });
                } else {
                    tg.showPopup({
                        title: '❌ Error',
                        message: data.message || 'Withdrawal failed.',
                        buttons: [{type: 'ok'}]
                    });
                }
            });
        });
    }
}

// Export for HTML
window.navigateTo = navigateTo;
window.goBack = goBack;
window.copyAddress = copyAddress;
window.copyReferral = copyReferral;
window.checkDeposit = checkDeposit;
window.investField = investField;
window.filterHistory = filterHistory;
window.saveWallet = saveWallet;