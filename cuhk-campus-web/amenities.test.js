import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { enrichAmenities } from './src/data/campusData.js';
import { searchBuildings } from './search.js';

test('published campus amenities have usable coordinates and support dining/transit searches', () => {
  const { items } = JSON.parse(readFileSync(new URL('./public/campus/amenities.json', import.meta.url)));
  assert.ok(items.some(p => p.type === 'canteen'));
  assert.ok(items.some(p => p.type === 'bus_stop'));
  assert.equal(new Set(items.map(p => p.id)).size, items.length);
  for (const p of items) {
    assert.ok(['canteen', 'bus_stop'].includes(p.type));
    assert.equal(p.position.length, 3);
    assert.ok(p.position.every(Number.isFinite));
    assert.ok(Math.abs(p.position[0]) < 1500 && Math.abs(p.position[2]) < 1500, `${p.name} must fit this campus model`);
    assert.ok(p.position[1] >= 0 && p.position[1] < 400);
    assert.match(p.source, /^https:\/\//);
    assert.ok(p.name || p.name_zh);
  }
  const places = enrichAmenities(items);
  for (const [query, type] of [['饭堂','canteen'],['食堂','canteen'],['公交站','bus_stop'],['校巴站','bus_stop']]) {
    const matches = searchBuildings(places, query, 100);
    assert.equal(matches.length, places.filter(p => p.type === type).length);
    assert.ok(matches.every(p => p.type === type));
  }
  const newAsia = places.find(p => /新亞/.test(p.name_zh));
  if (newAsia) assert.ok(searchBuildings(places,'新亚').includes(newAsia));
  const eastStops=places.filter(p=>/環迴東/.test(p.name_zh));
  assert.deepEqual(searchBuildings(places,'环回东').map(p=>p.id),eastStops.map(p=>p.id));
});
