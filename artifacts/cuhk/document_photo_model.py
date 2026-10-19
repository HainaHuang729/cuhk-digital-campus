"""Write the reconstruction ledger and assemble the final rendered contact sheet."""
from pathlib import Path
import json
from PIL import Image,ImageDraw,ImageFont
root=Path(__file__).resolve().parent
data=json.loads((root/'photo_rebuild_report.json').read_text('utf-8'))
refs=json.loads((root/'photo_reference_manifest.json').read_text('utf-8'))
lookup={str(v['osm_id']):v for v in refs}
landmark_data=json.loads((Path.home()/'.agent-reach/cuhk/landmarks/landmarks.json').read_text('utf-8'))
(root/'landmark_photo_references.json').write_text(json.dumps(landmark_data,ensure_ascii=False,indent=2),encoding='utf-8')
text=f'''# CUHK 照片参考重建 · 2026-09-10

最新模型：`CUHK_photo_rebuilt.blend`。这是 Blender / Cycles 输出，UE5 安装与导入已按用户要求暂停。

151 处已有名称全部搜索。模型中 {data['photo_guided_facades']} 处按照片更新外观，{data['design_guided_facades']} 处按校方设计效果图近似建模；另有 {data['unverified_facades']} 处因缺图、仅有室内/场地图或身份无法核实，保留原示意体量。照片含单视角、组合远景及历史照片，不是全部当前实景测绘。

## 交付

- `CUHK_photo_rebuilt.blend`：含地形、平滑道路、建筑、材质及楼名，默认相机为核心校园鸟瞰。
- `CUHK_photo_rebuilt_preview.png`：3600 × 2700 无标签主图。
- `CUHK_photo_rebuilt_labeled.png`：3600 × 2700 带楼名主图。
- `CUHK_photo_rebuilt_plan.png`：4000 × 4400 全校园带楼名俯视。
- `CUHK_landmarks_gallery.png` 与 `landmark_previews/`：六栋重点建筑近景。
- `photo_reference_manifest.json`、`landmark_photo_references.json`：逐栋来源链接、图片缓存路径、实际视觉审查范围、外观描述。
- `photo_rebuild_report.json`：逐栋已实施外观类型和未核实清单。

## 本轮改动

替换有照片依据建筑原先统一的窗格及随机屋顶配色，重做条带窗、深竖肋、遮阳板、阳台、彩色板、局部坡屋顶与外墙材料。图书馆、邵逸夫堂、科学馆礼堂、李兆基建筑学大楼、康本国际学术园、罗桂祥阁六栋另行重做主要体量；狮子亭改为红柱、绿色攒尖顶。建筑学大楼等基础向下接到现有显示地形，旧通用细节叠加已移除。

原始建筑和细节保留在源文件/隐藏对象中；新版位于 `11 Photo reference architecture`。照片用于外观观察，不是贴在方盒上的整楼照片纹理。素材无需联网即可渲染，材质与中文标签字体保存在 blend 中。

## 精度与使用

这是依据照片修正的校园概念模型。OSM 平面位置和原有地形仍是定位基础；窗列间距、背面、未拍到的屋顶和精确高度未测绘。图书馆约 19m、罗桂祥阁约 18m、狮子亭约 4.9m 为明确估算。陈震夏宿舍校方文字为十层，本模型按 3.3m/层估高。组合照片中的宿舍只使用共有外观特征，不能据此认定每一面相同。

楼名取自原 OSM 标签，205 处校园建筑中 151 有名称、54 使用无名称占位符。标签是针对相机布置的可编辑三维文字；切换相机时需重新调用 `building_labels.apply_building_labels(camera, mode)`。关闭 `10 Building labels / OSM names` 的渲染即可看无标签场景。

地形与道路延续上一版的显示整平；原始 DTM 仍在 `terrain.npz`。源地形标称精度 ±5m，本模型不用于施工或测绘。

## 主要来源

- [中大官方校园地图](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html)
- [中大校园发展处项目照片](https://www.cdo.cuhk.edu.hk/projects/)
- [地政总署 5m DTM](https://data.gov.hk/en-data/dataset/hk-landsd-openmap-5m-grid-dtm)
- [OpenStreetMap contributors，ODbL](https://www.openstreetmap.org/copyright)

UE5：Epic Launcher 已安装至 E:/Epic Games，引擎尚未下载、未导入或渲染。`ue5/` 内脚本为待用交接文件。

## 逐栋重建记录

| 建筑 | 本轮状态 | 可见外观类型 | 参考 |
|---|---|---|---|
'''
status={'photo_guided_facade':'照片近似外观','design_guided_facade':'校方设计图近似','unverified_exterior':'外观未核实，保留示意'}
for r in data['records']:
    row=lookup.get(str(r['osm_id']),{})
    name=r.get('name') or row.get('name_zh') or row.get('name_en') or r['osm_id']
    url=r.get('source_page') or row.get('source_page')
    link=f'[来源]({url})' if url else '无确认图片'
    text+=f"| {name.replace('|','/')} | {status[r['status']]} | {r.get('facade_style','—')} | {link} |\n"
(root/'PHOTO_RECONSTRUCTION.md').write_text(text,encoding='utf-8')
names=[('library','大学图书馆'),('shaw_hall','邵逸夫堂'),('science','科学馆礼堂'),('architecture','李兆基建筑学大楼'),('yasumoto','康本国际学术园'),('lo_kwee_seong','罗桂祥阁')]
W=2700;tile=860;gap=30;top=140;caption=82;H=top+2*(645+caption+gap)+30
sheet=Image.new('RGB',(W,H),'#eef1ee');draw=ImageDraw.Draw(sheet)
font='C:/Windows/Fonts/msyh.ttc'
title=ImageFont.truetype(font,46);small=ImageFont.truetype(font,24);label=ImageFont.truetype(font,32)
draw.text((30,24),'香港中文大学 · 照片参考重建',font=title,fill='#182a2d')
draw.text((32,88),'Blender / Cycles   ·   六栋重点建筑   ·   外观与尺度近似',font=small,fill='#52666a')
for index,(file,name) in enumerate(names):
    image=Image.open(root/'landmark_previews'/f'{file}.png').convert('RGB');image.thumbnail((tile,645),Image.Resampling.LANCZOS)
    x=30+(index%3)*(tile+gap);y=top+(index//3)*(645+caption+gap)
    sheet.paste(image,(x,y));draw.text((x,y+663),f'{index+1:02d}  {name}',font=label,fill='#182a2d')
sheet.save(root/'CUHK_landmarks_gallery.png')
print('PHOTO_DOCUMENTATION_COMPLETE',data['photo_guided_facades'],data['design_guided_facades'],data['unverified_facades'])
