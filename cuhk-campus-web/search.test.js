import { test } from 'node:test';
import assert from 'node:assert/strict';
import { normalize, searchBuildings } from './search.js';
test('search accepts simplified, traditional, English punctuation and source IDs', () => {
  const buildings = [
    { id: '134410449', name_zh: '大學圖書館', name: 'University Library', campus: true },
    { id: '134408696', name_zh: '錢穆圖書館', name: "Ch’ien Mu Library", campus: true },
    { id: '3', name_zh: '圖書館附屬樓', name: 'Library Annex', campus: false },
  ];
  assert.equal(normalize('大学图书馆'), normalize('大學圖書館'));
  assert.equal(searchBuildings(buildings, '大学图书馆')[0].id, '134410449');
  assert.equal(searchBuildings(buildings, 'CHIEN MU')[0].id, '134408696');
  assert.equal(searchBuildings(buildings, '134410449')[0].name, 'University Library');
  assert.equal(searchBuildings(buildings, '图书馆').length, 3);
  assert.deepEqual(searchBuildings(buildings, '不存在'), []);
  assert.deepEqual(searchBuildings(buildings, '  '), []);
});
