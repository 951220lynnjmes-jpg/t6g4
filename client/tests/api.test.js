import { describe, expect, it, vi } from 'vitest';
import { createTodoApi } from '../src/api.js';

function jsonResponse(body, status = 200) {
    return {
        ok: status >= 200 && status < 300,
        status,
        json: async () => body,
    };
}

describe('createTodoApi', () => {
    it('取得待辦事項列表', async () => {
        const fetchMock = vi.fn().mockResolvedValue(
            jsonResponse([{ id: 1, title: '買牛奶', completed: false }]),
        );
        const api = createTodoApi(fetchMock);

        await expect(api.list()).resolves.toEqual([
            { id: 1, title: '買牛奶', completed: false },
        ]);
        expect(fetchMock).toHaveBeenCalledWith(
            '/api/todos',
            expect.objectContaining({
                headers: { 'Content-Type': 'application/json' },
            }),
        );
    });

    it('以 JSON 內容新增待辦事項', async () => {
        const created = { id: 7, title: '寫測試', completed: false };
        const fetchMock = vi.fn().mockResolvedValue(jsonResponse(created, 201));
        const api = createTodoApi(fetchMock);

        await expect(api.create('寫測試')).resolves.toEqual(created);
        expect(fetchMock).toHaveBeenCalledWith(
            '/api/todos',
            expect.objectContaining({
                method: 'POST',
                body: JSON.stringify({ title: '寫測試' }),
            }),
        );
    });

    it('更新指定待辦事項', async () => {
        const updated = { id: 7, title: '寫測試', completed: true };
        const fetchMock = vi.fn().mockResolvedValue(jsonResponse(updated));
        const api = createTodoApi(fetchMock);

        await expect(api.update(7, { completed: true })).resolves.toEqual(updated);
        expect(fetchMock).toHaveBeenCalledWith(
            '/api/todos/7',
            expect.objectContaining({
                method: 'PATCH',
                body: JSON.stringify({ completed: true }),
            }),
        );
    });

    it('刪除待辦事項時處理 204 回應', async () => {
        const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 204 });
        const api = createTodoApi(fetchMock);

        await expect(api.remove(7)).resolves.toBeNull();
        expect(fetchMock).toHaveBeenCalledWith(
            '/api/todos/7',
            expect.objectContaining({ method: 'DELETE' }),
        );
    });

    it('將伺服器錯誤訊息轉為 Error', async () => {
        const fetchMock = vi
            .fn()
            .mockResolvedValue(jsonResponse({ error: '找不到待辦事項' }, 404));
        const api = createTodoApi(fetchMock);

        await expect(api.update(99, { completed: true })).rejects.toThrow(
            '找不到待辦事項',
        );
    });

    it('沒有 JSON 內容時使用狀態碼產生錯誤訊息', async () => {
        const fetchMock = vi.fn().mockResolvedValue({
            ok: false,
            status: 500,
            json: async () => {
                throw new Error('not json');
            },
        });
        const api = createTodoApi(fetchMock);

        await expect(api.list()).rejects.toThrow('請求失敗（500）');
    });

    it('沒有可用的 fetch 時立即報錯', () => {
        expect(() => createTodoApi(null)).toThrow('找不到可用的 fetch 實作');
    });
});
