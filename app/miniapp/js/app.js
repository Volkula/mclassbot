// Инициализация Telegram WebApp
const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();

// API базовый URL
const API_BASE = '/api';

// Состояние приложения
let currentView = 'events-list';
let currentEvent = null;
let events = [];
let initData = '';

// Получаем initData от Telegram
if (tg.initData) {
    initData = tg.initData;
}

// Инициализация приложения
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    loadEvents();
});

// Настройка обработчиков событий
function setupEventListeners() {
    document.getElementById('back-btn').addEventListener('click', () => {
        showView('events-list');
    });

    document.getElementById('back-to-events').addEventListener('click', () => {
        showView('events-list');
    });

    document.getElementById('registration-form').addEventListener('submit', handleRegistration);
}

// Показать представление
function showView(viewName) {
    document.querySelectorAll('.container').forEach(el => el.classList.add('hidden'));
    document.getElementById(viewName).classList.remove('hidden');
    currentView = viewName;
}

// Показать загрузку
function showLoading() {
    document.getElementById('loading').classList.remove('hidden');
}

// Скрыть загрузку
function hideLoading() {
    document.getElementById('loading').classList.add('hidden');
}

// Показать сообщение
function showMessage(text, type = 'info') {
    const messageEl = document.getElementById('message');
    messageEl.textContent = text;
    messageEl.className = `message ${type}`;
    messageEl.classList.remove('hidden');
    
    setTimeout(() => {
        messageEl.classList.add('hidden');
    }, 3000);
}

// Загрузить события
async function loadEvents() {
    showLoading();
    try {
        const response = await fetch(`${API_BASE}/events/`);
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`Ошибка загрузки событий: ${response.status} - ${errorText}`);
        }
        const data = await response.json();
        console.log('Загружены события:', data);
        events = data.events || [];
        console.log('Количество событий:', events.length);
        renderEvents();
    } catch (error) {
        console.error('Ошибка загрузки событий:', error);
        showMessage('Ошибка загрузки событий: ' + error.message, 'error');
    } finally {
        hideLoading();
    }
}

// Отобразить события
function renderEvents() {
    const container = document.getElementById('events-container');
    
    if (!container) {
        console.error('Контейнер events-container не найден');
        return;
    }
    
    if (events.length === 0) {
        container.innerHTML = '<div class="empty-state"><p>Нет доступных событий</p><p style="font-size: 12px; color: #999; margin-top: 10px;">Убедитесь, что события созданы и имеют статус "Утверждено" или "Активно"</p></div>';
        return;
    }
    
    container.innerHTML = events.map(event => `
        <div class="event-card" onclick="showEventDetail(${event.id})">
            <h3>${escapeHtml(event.title)}</h3>
            <div class="date">📅 ${formatDateTime(event.date_time)}</div>
            ${event.description ? `<div class="description">${escapeHtml(event.description)}</div>` : ''}
            <span class="status">${event.status === 'active' ? 'Активно' : 'Доступно'}</span>
        </div>
    `).join('');
}

// Показать детали события
async function showEventDetail(eventId) {
    showLoading();
    try {
        const response = await fetch(`${API_BASE}/events/${eventId}`);
        if (!response.ok) {
            throw new Error('Событие не найдено');
        }
        const event = await response.json();
        currentEvent = event;
        renderEventDetail(event);
        showView('event-detail');
    } catch (error) {
        showMessage('Ошибка загрузки события: ' + error.message, 'error');
    } finally {
        hideLoading();
    }
}

// Отобразить детали события
function renderEventDetail(event) {
    const infoEl = document.getElementById('event-info');
    let photoHtml = '';
    if (event.photo_file_id) {
        photoHtml = `<img src="${API_BASE}/events/${event.id}/photo" 
                     alt="${escapeHtml(event.title)}" 
                     style="width: 100%; border-radius: 12px; margin-bottom: 16px; max-height: 300px; object-fit: cover;" 
                     onerror="this.style.display='none'">`;
    }
    infoEl.innerHTML = `
        ${photoHtml}
        <h2>${escapeHtml(event.title)}</h2>
        <div class="date">📅 ${formatDateTime(event.date_time)}</div>
        ${event.description ? `<div class="description">${escapeHtml(event.description)}</div>` : ''}
    `;
    
    const formFieldsEl = document.getElementById('form-fields');
    formFieldsEl.innerHTML = event.fields.map(field => {
        let input = '';
        
        if (field.field_type === 'select' && field.options) {
            input = `
                <select name="${field.field_name}" ${field.required ? 'required' : ''}>
                    <option value="">Выберите...</option>
                    ${field.options.map(opt => `<option value="${escapeHtml(opt)}">${escapeHtml(opt)}</option>`).join('')}
                </select>
            `;
        } else if (field.field_type === 'text') {
            input = `<textarea name="${field.field_name}" ${field.required ? 'required' : ''}></textarea>`;
        } else {
            const inputType = field.field_type === 'email' ? 'email' : 
                             field.field_type === 'phone' ? 'tel' : 
                             field.field_type === 'date' ? 'date' : 
                             field.field_type === 'number' ? 'number' : 'text';
            input = `<input type="${inputType}" name="${field.field_name}" ${field.required ? 'required' : ''}>`;
        }
        
        return `
            <div class="form-group">
                <label>
                    ${escapeHtml(field.field_name)}
                    ${field.required ? '<span class="required">*</span>' : ''}
                </label>
                ${input}
            </div>
        `;
    }).join('');
}

// Обработка регистрации
async function handleRegistration(e) {
    e.preventDefault();
    
    if (!initData) {
        showMessage('Ошибка авторизации. Пожалуйста, откройте приложение через Telegram.', 'error');
        return;
    }
    
    const formData = new FormData(e.target);
    const data = {};
    
    for (const [key, value] of formData.entries()) {
        data[key] = value;
    }
    
    showLoading();
    
    try {
        const response = await fetch(`${API_BASE}/registrations/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Init-Data': initData
            },
            body: JSON.stringify({
                event_id: currentEvent.id,
                data: data
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Ошибка регистрации');
        }
        
        const result = await response.json();
        showMessage('Вы успешно зарегистрированы!', 'success');
        
        setTimeout(() => {
            showView('events-list');
            loadEvents();
        }, 1500);
    } catch (error) {
        showMessage('Ошибка регистрации: ' + error.message, 'error');
    } finally {
        hideLoading();
    }
}

// Загрузить мои регистрации
async function loadMyRegistrations() {
    if (!initData) {
        showMessage('Ошибка авторизации', 'error');
        return;
    }
    
    showLoading();
    try {
        const response = await fetch(`${API_BASE}/registrations/my`, {
            headers: {
                'X-Init-Data': initData
            }
        });
        
        if (!response.ok) {
            throw new Error('Ошибка загрузки регистраций');
        }
        
        const registrations = await response.json();
        renderRegistrations(registrations);
        showView('my-registrations');
    } catch (error) {
        showMessage('Ошибка загрузки регистраций: ' + error.message, 'error');
    } finally {
        hideLoading();
    }
}

// Отобразить регистрации
function renderRegistrations(registrations) {
    const container = document.getElementById('registrations-container');
    
    if (registrations.length === 0) {
        container.innerHTML = '<div class="empty-state"><p>У вас нет регистраций</p></div>';
        return;
    }
    
    container.innerHTML = registrations.map(reg => {
        const event = events.find(e => e.id === reg.event_id);
        const eventTitle = event ? event.title : `Событие #${reg.event_id}`;
        
        const dataHtml = Object.entries(reg.data).map(([key, value]) => `
            <div class="data-item">
                <span class="data-label">${escapeHtml(key)}:</span>
                <span>${escapeHtml(String(value))}</span>
            </div>
        `).join('');
        
        return `
            <div class="registration-card">
                <h3>${escapeHtml(eventTitle)}</h3>
                <div class="date">Зарегистрирован: ${formatDateTime(reg.created_at)}</div>
                <div class="data">${dataHtml}</div>
            </div>
        `;
    }).join('');
}

// Утилиты
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatDateTime(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString('ru-RU', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// Добавляем кнопку "Мои регистрации" в главное меню
document.addEventListener('DOMContentLoaded', () => {
    const eventsList = document.getElementById('events-list');
    if (eventsList) {
        const header = eventsList.querySelector('h1');
        if (header && initData) {
            const myRegBtn = document.createElement('button');
            myRegBtn.textContent = '📋 Мои регистрации';
            myRegBtn.className = 'submit-btn';
            myRegBtn.style.marginTop = '20px';
            myRegBtn.onclick = loadMyRegistrations;
            eventsList.insertBefore(myRegBtn, eventsList.firstChild.nextSibling);
        }
    }
});

