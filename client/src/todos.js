export const MAX_TITLE_LENGTH = 200;

export function normalizeTitle(rawTitle) {
    const title = typeof rawTitle === 'string' ? rawTitle.trim() : '';

    if (!title) {
        throw new Error('請輸入待辦事項內容');
    }
    if (title.length > MAX_TITLE_LENGTH) {
        throw new Error(`內容不可超過 ${MAX_TITLE_LENGTH} 個字元`);
    }

    return title;
}

export function filterTodos(todos, filter) {
    if (filter === 'active') {
        return todos.filter((todo) => !todo.completed);
    }
    if (filter === 'completed') {
        return todos.filter((todo) => todo.completed);
    }
    return todos.slice();
}

export function summarize(todos) {
    const completed = todos.filter((todo) => todo.completed).length;

    return {
        total: todos.length,
        active: todos.length - completed,
        completed,
    };
}
