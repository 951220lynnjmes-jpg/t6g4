import { describe, expect, it } from 'vitest';
import {
    MAX_TITLE_LENGTH,
    filterTodos,
    normalizeTitle,
    summarize,
} from '../src/todos.js';

const todos = [
    { id: 1, title: '買牛奶', completed: false },
    { id: 2, title: '寫測試', completed: true },
    { id: 3, title: '跑步', completed: false },
];

describe('normalizeTitle', () => {
    it('去除前後空白', () => {
        expect(normalizeTitle('  買牛奶  ')).toBe('買牛奶');
    });

    it('拒絕空白字串', () => {
        expect(() => normalizeTitle('   ')).toThrow('請輸入待辦事項內容');
    });

    it('拒絕非字串輸入', () => {
        expect(() => normalizeTitle(null)).toThrow('請輸入待辦事項內容');
    });

    it('接受長度上限', () => {
        const title = 'a'.repeat(MAX_TITLE_LENGTH);
        expect(normalizeTitle(title)).toBe(title);
    });

    it('拒絕超過長度上限', () => {
        expect(() => normalizeTitle('a'.repeat(MAX_TITLE_LENGTH + 1))).toThrow(
            `內容不可超過 ${MAX_TITLE_LENGTH} 個字元`,
        );
    });
});

describe('filterTodos', () => {
    it('全部篩選回傳新的陣列', () => {
        const result = filterTodos(todos, 'all');

        expect(result).toEqual(todos);
        expect(result).not.toBe(todos);
    });

    it('只回傳未完成項目', () => {
        expect(filterTodos(todos, 'active').map((todo) => todo.id)).toEqual([1, 3]);
    });

    it('只回傳已完成項目', () => {
        expect(filterTodos(todos, 'completed').map((todo) => todo.id)).toEqual([2]);
    });

    it('未知篩選條件時回傳全部', () => {
        expect(filterTodos(todos, 'unknown')).toEqual(todos);
    });
});

describe('summarize', () => {
    it('計算總數、未完成與已完成', () => {
        expect(summarize(todos)).toEqual({
            total: 3,
            active: 2,
            completed: 1,
        });
    });

    it('空清單的統計皆為零', () => {
        expect(summarize([])).toEqual({
            total: 0,
            active: 0,
            completed: 0,
        });
    });
});
