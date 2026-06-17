// PlantUSDT Mini App - JavaScript

// Telegram WebApp
let tg = window.Telegram.WebApp;

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    tg.ready();
    tg.expand();
    
    // Load user data
    loadUserData();
    
    // Set up event listeners
    setupEventListeners();
});

// Navigation
function navigateTo(page) {
    if (page === 'dashboard') {
        window.location.href = 'dashboard.html';
    } else if (page === 'deposit') {
        window.location.href = 'deposit.html';
    } else if (page === 'invest') {
        window.location.href = 'invest.html';
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
        const response = await fetch('/api/user');
        const data = await response.json();
        
        if (data.success) {
            updateUI(data);
        }
    } catch (error) {
        console.error('Error loading user data:', error);
    }
}

// Update UI with user data
function updateUI(data) {
    // Update balances
    const balanceElements = document.querySelectorAll('.balance-amount, #balance, #dashBalance, #investBalance, #withdrawBalance');
    balanceElements.forEach(el => {
        if (el.id === 'balance' || el.id === 'dashBalance' || el.id === 'investBalance' || el.id === 'withdrawBalance') {
            el.textContent = `$${data.balance?.toFixed(2) || '0.00'}`;
        }
    });
    
    // Update dashboard stats
    if (document.getElementById('dashInvested')) {
        document.getElementById('dashInvested').textContent = `$${data.total_invested?.toFixed(2) || '0.00'}`;
    }
    if (document.getElementById('dashEarned')) {
        document.getElementById('dashEarned').textContent = `$${data.total_earned?.toFixed(2) || '0.00'}`;
    }
    if (document.getElementById('dashDeposited')) {
        document.getElementById('dashDeposited').textContent = `$${data.total_deposited?.toFixed(2) || '0.00'}`;
    }
    if (document.getElementById('dashReferrals')) {
        document.getElementById('dashReferrals').textContent = data.referrals || 0;
    }
}

// Copy address to clipboard
function copyAddress() {
    const address = document.getElementById('addressText').textContent;
    navigator.clipboard.writeText(address).then(() => {
        tg.showPopup({
            title: '✅ Copied!',
            message: 'Wallet address copied to clipboard',
            buttons: [{type: 'ok'}]
        });
    });
}

// Copy referral link
function copyReferral() {
    const tgUser = tg.initDataUnsafe?.user;
    if (tgUser) {
        const link = `https://t.me/PlantUSDT_bot?start=${tgUser.id}`;
        navigator.clipboard.writeText(link).then(() => {
            tg.showPopup({
                title: '✅ Copied!',
                message: 'Referral link copied! Share it with your friends.',
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
            const response = await fetch('/api/check_deposit');
            const data = await response.json();
            
            if (data.success) {
                statusDiv.innerHTML = '✅ Deposit detected! Your balance has been updated.';
            } else {
                statusDiv.innerHTML = '⏳ No new deposits found. Please wait 5-15 minutes.';
            }
        } catch (error) {
            statusDiv.innerHTML = '❌ Error checking deposits. Please try again.';
        }
    }
}

// Set wallet address
function setWallet() {
    tg.showPopup({
        title: '💳 Set Wallet',
        message: 'Enter your BSC wallet address:',
        buttons: [
            {type: 'cancel'},
            {type: 'ok'}
        ]
    });
}

// Filter history
function filterHistory(type) {
    // Remove active class from all filter buttons
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Add active class to clicked button
    event.target.classList.add('active');
    
    // Show loading
    const historyList = document.getElementById('historyList');
    historyList.innerHTML = '<p class="empty-state">Loading...</p>';
    
    // Fetch filtered history
    fetch(`/api/history?type=${type}`)
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
    // Withdraw form
    const withdrawForm = document.getElementById('withdrawForm');
    if (withdrawForm) {
        withdrawForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const amount = document.getElementById('withdrawAmount').value;
            const address = document.getElementById('withdrawAddress').value;
            
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
            
            // Send withdrawal request to bot
            fetch('/api/withdraw', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
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

// Export for use in HTML
window.navigateTo = navigateTo;
window.goBack = goBack;
window.copyAddress = copyAddress;
window.copyReferral = copyReferral;
window.checkDeposit = checkDeposit;
window.setWallet = setWallet;
window.filterHistory = filterHistory;