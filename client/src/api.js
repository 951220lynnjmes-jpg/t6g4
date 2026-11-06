async function request(fetchImpl, url, options = {}) {
    const response = await fetchImpl(url, {
        headers: { 'Content-Type': 'application/json' },
        ...options,
    });

    if (response.status === 204) {
        return null;
    }

    const data = await response.json().catch(() => null);

    if (!response.ok) {
        throw new Error(data?.error || `請求失敗（${response.status}）`);
    }

    return data;
}

export function createTodoApi(fetchImpl = globalThis.fetch) {
    if (typeof fetchImpl !== 'function') {
        throw new Error('找不到可用的 fetch 實作');
    }

    return {
        list: () => request(fetchImpl, '/api/todos'),
        create: (title) =>
            request(fetchImpl, '/api/todos', {
                method: 'POST',
                body: JSON.stringify({ title }),
            }),
        update: (id, changes) =>
            request(fetchImpl, `/api/todos/${id}`, {
                method: 'PATCH',
                body: JSON.stringify(changes),
            }),
        remove: (id) =>
            request(fetchImpl, `/api/todos/${id}`, {
                method: 'DELETE',
            }),
    };
}
