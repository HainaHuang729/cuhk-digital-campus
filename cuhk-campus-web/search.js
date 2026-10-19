// Accept common simplified queries while preserving names from the source map.
const traditional = '圖書館學樓國際體育場實驗綜學會議邵邊聯誼禮賓馬嶺東華樂鳳蓮陳鄭龍黃錢萬聲榮藝醫廣區賽廳曉資訊科學研創術獎鄧長風漢環護蘭濤雲樹門幹園蘇業麗傑謙崗鐵運動劉張陸馮孫臺灣圓圍與';
const simplified = '图书馆学楼国际体育场实验综学会议邵边联谊礼宾马岭东华乐凤莲陈郑龙黄钱万声荣艺医广区赛厅晓资讯科学研创术奖邓长风汉环护兰涛云树门干园苏业丽杰谦岗铁运动刘张陆冯孙台湾圆围与';
const characterMap = new Map([...traditional].map((c, i) => [c, simplified[i]]));
for (const [a,b] of Object.entries({'飯':'饭','飲':'饮','車':'车','總':'总','線':'线','綫':'线','眾':'众','達':'达','賢':'贤','豐':'丰','嵐':'岚','莊':'庄','廚':'厨','亞':'亚','興':'兴','迴':'回'})) characterMap.set(a,b);
export function normalize(value) {
  return [...String(value ?? '').toLocaleLowerCase()].map(c => characterMap.get(c) ?? c).join('').replace(/[\s·\-_'’()（）.,]/g, '');
}
export function searchBuildings(buildings, query, limit = 30) {
  const needle = normalize(query);
  if (!needle) return [];
  return buildings.map(building => {
    const names = [building.name_zh, building.name, building.id, ...(building.aliases || [])].map(normalize);
    const score = names.some(n => n === needle) ? 0 : names.some(n => n.startsWith(needle)) ? 1 : names.some(n => n.includes(needle)) ? 2 : 3;
    return { building, score };
  }).filter(item => item.score < 3).sort((a, b) => a.score - b.score || Number(b.building.campus) - Number(a.building.campus)).slice(0, limit).map(item => item.building);
}
