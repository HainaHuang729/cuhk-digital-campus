export const views = {
  overview: { position: [1370, 1140, 1460], target: [0, 60, -65], label: '山海全景', caption: 'HILLSIDE TO HARBOUR' },
  central: { position: [365, 435, 565], target: [-110, 95, 0], label: '中央校园', caption: 'THE HEART OF CAMPUS' },
  hill: { position: [525, 615, 455], target: [-120, 140, -245], label: '山上书院', caption: 'AMONG THE HILLS' },
  coast: { position: [1370, 720, -1170], target: [50, 80, -80], label: '沿海漫游', caption: 'LOOKING TO THE SEA' },
};

export const placeDetails = {
  '134410449': { type: 'Library', description: '从中央校园走向图书馆。换一个角度，观察阅读空间与山坡之间的关系。' },
  '107139030': { type: 'Culture', description: '邵逸夫堂。校园中的演出与集会空间，在中央校园的建筑群之间找到它。' },
  '134408696': { type: 'Library', description: '钱穆图书馆。沿着书院的道路，探索山上校园。' },
  '135156315': { type: 'Place of worship', description: '崇基学院礼拜堂。靠近后，观察这座建筑与周围绿地的关系。' },
  '135312912': { type: 'Research', description: '何善衡工程学大楼。工程教学与科研建筑群的一部分。' },
  '107139044': { type: 'Research', description: '六层的山坡实验室建筑。五排彩色幕墙、深色端部和高低相接的入口，回应校园地形。',
    stories: [
      { year: 2007, title: '山坡上的实验室', text: '中大的中央科学实验室大楼获得香港建筑师学会奖。校方介绍这座六层建筑，其中五层作为实验室。彩色幕墙成为校园中容易辨认的立面。', image: '/images/shaw-science.jpg', imageAlt: '中大官方照片中的逸夫科学大楼彩色幕墙', source: 'https://www.cpr.cuhk.edu.hk/tc/press/cuhks-centralized-labs-wins-hong-kong-institute-of-architects-award/', sourceLabel: '中大新闻 · 建筑获奖' },
      { year: 2011, title: '逸夫科学大楼', text: '大楼于2011年举行命名典礼，命名为逸夫科学大楼。今天的数字模型结合校方照片和地形高程，呈现它在山坡上的体量关系。', image: '/images/shaw-science.jpg', imageAlt: '逸夫科学大楼外观', source: 'https://www.cpr.cuhk.edu.hk/tc/press/naming-ceremony-of-run-run-shaw-science-building-at-cuhk-held-today/', sourceLabel: '中大新闻 · 命名典礼' },
    ],
  },
};

export const featuredIds = ['134410449','107139044','107139030','134408696','135156315','135312912'];
export function enrichBuildings(rows) {
  return rows.map(row => ({ ...row, id: String(row.id), type: 'Campus architecture', year: null, stories: [],
    description: '沿着校园地形，探索这栋建筑与周围空间。模型外观与高度包含估算。', ...placeDetails[row.id] }));
}

export function enrichAmenities(rows) {
  return rows.map(row => ({
    ...row, id: String(row.id), poi: true, campus: true,
    name_zh: row.name_zh || row.name, name: row.name_en || row.name,
    size: row.size || [22, 8, 22], year: null, stories: [],
    aliases: [...(row.aliases || []), ...(row.type === 'canteen' ? ['食堂', '饭堂', '餐厅', 'canteen', 'dining'] : ['公交站', '校巴站', '巴士站', 'bus stop'])],
    description: row.description || (row.type === 'canteen' ? '校园餐饮地点。' : '校园及邻近公共交通停靠点。'),
  }));
}
