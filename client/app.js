import { createTodoApi } from './src/api.js';
import { filterTodos, normalizeTitle, summarize } from './src/todos.js';

const api = createTodoApi();
const state = {
    todos: [],
    filter: 'all',
};

const form = document.querySelector('[data-testid="todo-form"]');
const input = document.getElementById('new-todo');
const list = document.querySelector('[data-testid="todo-list"]');
const errorMessage = document.querySelector('[data-testid="error"]');
const remaining = document.querySelector('[data-testid="remaining"]');
const emptyState = document.querySelector('[data-testid="empty-state"]');
const filterButtons = [...document.querySelectorAll('[data-filter]')];

function showError(message) {
    errorMessage.textContent = message;
    errorMessage.hidden = false;
}

function clearError() {
    errorMessage.textContent = '';
    errorMessage.hidden = true;
}

function createItem(todo) {
    const item = document.createElement('li');
    item.className = 'todo-item';
    item.dataset.id = String(todo.id);
    item.dataset.testid = 'todo-item';
    item.classList.toggle('completed', todo.completed);

    const toggle = document.createElement('input');
    toggle.type = 'checkbox';
    toggle.checked = todo.completed;
    toggle.dataset.testid = 'toggle';
    toggle.setAttribute('aria-label', `完成：${todo.title}`);

    const title = document.createElement('span');
    title.className = 'title';
    title.textContent = todo.title;

    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'delete';
    remove.dataset.testid = 'delete';
    remove.textContent = '刪除';
    remove.setAttribute('aria-label', `刪除：${todo.title}`);

    item.append(toggle, title, remove);
    return item;
}

function render() {
    const stats = summarize(state.todos);
    const visible = filterTodos(state.todos, state.filter);

    remaining.textContent = `${stats.active} 項未完成`;
    list.replaceChildren(...visible.map(createItem));
    emptyState.hidden = visible.length > 0;

    for (const button of filterButtons) {
        const isActive = button.dataset.filter === state.filter;
        button.classList.toggle('active', isActive);
        button.setAttribute('aria-pressed', String(isActive));
    }
}

async function load() {
    try {
        state.todos = await api.list();
        render();
    } catch (error) {
        showError(`無法載入待辦事項：${error.message}`);
    }
}

async function run(action) {
    try {
        clearError();
        await action();
        await load();
    } catch (error) {
        showError(error.message);
    }
}

form.addEventListener('submit', (event) => {
    event.preventDefault();

    run(async () => {
        const title = normalizeTitle(input.value);
        await api.create(title);
        input.value = '';
        input.focus();
    });
});

list.addEventListener('change', (event) => {
    const toggle = event.target.closest('[data-testid="toggle"]');
    if (!toggle) {
        return;
    }

    const id = Number(toggle.closest('[data-id]').dataset.id);
    run(() => api.update(id, { completed: toggle.checked }));
});

list.addEventListener('click', (event) => {
    const button = event.target.closest('[data-testid="delete"]');
    if (!button) {
        return;
    }

    const id = Number(button.closest('[data-id]').dataset.id);
    run(() => api.remove(id));
});

for (const button of filterButtons) {
    button.addEventListener('click', () => {
        state.filter = button.dataset.filter;
        render();
    });
}

load();
