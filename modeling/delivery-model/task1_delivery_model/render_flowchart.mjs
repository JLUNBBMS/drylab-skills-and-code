// Lay out original scientific PNGs without redrawing their plotted data.
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {chromium} from 'playwright';
const root=path.dirname(fileURLToPath(import.meta.url));
const out=path.join(root,'output');
async function dataImage(relative){
 const bytes=await fs.readFile(path.join(root,relative));
 return 'data:image/png;base64,'+bytes.toString('base64');
}
const inputs=[
 ['A','模型与目标区域','figures/transport_schematic.png',
  '统一剂量 1 μg/cm² · 观察 24 h',
  '主指标：活性表皮与浅真皮合计保留量。两层暴露分别报告，底部流出量单独记录。','运输结构示意'],
 ['B','代理证据与条件校准','figures/fig10_boundary_consistency.png',
  '归一化形状 → 有限模型有效参数',
  '猪皮 tFNA 与脂质体采用同条件代理曲线；原始观测点与模型曲线共同呈现边界残差。','图10 · 边界一致性'],
 ['C','目标层保留量','figures/fig06_primary_endpoint.png',
  'tFNA 0.5864 · NLC 0.5824 μg/cm²',
  '两层合计基线差约 0.69%。总体保留接近，tFNA 的分布更偏向真皮。','图6 · 基线计算'],
 ['D','配对参数情景','figures/fig08_uncertainty_intervals.png',
  '256 组配对情景 · tFNA 排名第一频率 44.1%',
  '区间描述设定参数范围，频率描述情景排序。全部两两差值区间跨零。','图8 · 不确定性'],
 ['E','人体辅助迁移','figures/fig11_human_transfer.png',
  '直接迁移检查 → 人体数据辅助校准',
  '人体曲线约束跨条件有效参数。辅助拟合使用了人体观测，独立验证需要另取数据。','图11 · 条件性迁移'],
 ['F','持平条件与实验选择','figures/fig12_decision_boundaries.png',
  '黑线表示两层合计保留量持平',
  '固定参照基线，考察 tFNA 扩散与表面进入能力；优先测量能使判断跨越持平线的量。','图12 · 决策边界']
];
const cards=[];
for(const [letter,title,file,key,caption,source] of inputs){
 cards.push(`<section class="card"><h2><b>${letter}</b>${title}<small>${source}</small></h2><div class="visual"><img src="${await dataImage(file)}" alt="${title}"></div><div class="key">${key}</div><p>${caption}</p></section>`);
}
const stages=[['研究问题','是否值得优先验证 tFNA？'],['建立参照','游离 CK · NLC · 脂质体'],['代理校准','归一化数据约束有效参数'],['运输模拟','Donor → SC → VE → 真皮'],['数值验证','守恒 · 网格 · 求解器'],['迁移与情景','人体辅助校准 · 参数范围'],['实验决策','目标层保留 · 持平条件']];
const html=`<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>任务一：目标皮肤层递送潜力评估</title><style>
*{box-sizing:border-box}body{margin:0;background:white;color:#282521;font-family:'Microsoft YaHei',Arial,sans-serif}
main{width:3000px;padding:38px 44px 32px}h1{margin:0;color:#7e0909;font-size:66px;text-align:center;font-weight:750;letter-spacing:2px}
.subtitle{text-align:center;font-size:25px;margin:14px 0 26px;color:#5d5d2a}
.steps{display:grid;grid-template-columns:repeat(7,1fr);gap:24px;margin-bottom:28px}
.step{height:151px;border:3px solid #7e0909;border-radius:22px;padding:22px 12px;text-align:center;position:relative;background:#fffaf7}
.step:not(:last-child):after{content:'➜';position:absolute;right:-30px;top:45px;color:#c28d89;font-size:43px;z-index:2}
.step strong{display:block;color:#7e0909;font-size:31px;margin-bottom:14px}.step span{font-size:21px;white-space:nowrap}
.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:26px}
.card{border:3px solid #7e0909;border-radius:24px;height:680px;overflow:hidden;display:flex;flex-direction:column;padding:0 20px 14px}
h2{display:flex;align-items:center;gap:14px;height:70px;flex:none;font-size:31px;color:#7e0909;margin:0;border-bottom:1px solid #dec9bf;white-space:nowrap}
h2 b{font-size:39px}h2 small{margin-left:auto;font-size:17px;color:#77745d;font-weight:400}
.visual{height:425px;width:100%;display:flex;align-items:center;justify-content:center;flex:none;padding:6px 0}.visual img{width:100%;height:100%;object-fit:contain}
.card:first-child .visual img{width:90%}
.key{padding:12px 8px;text-align:center;background:#f6ece7;border-radius:12px;color:#7e0909;font-size:24px;font-weight:700;flex:none}
.card p{margin:12px 6px 0;font-size:22px;line-height:1.5}
footer{border:3px solid #777247;border-radius:20px;margin-top:26px;padding:18px 26px;display:grid;grid-template-columns:1fr 1fr;align-items:center;gap:28px}
footer strong{font-size:31px;color:#7e0909}footer p{font-size:23px;line-height:1.5;margin:8px 0 0}
.next{font-size:24px;line-height:1.7;border-left:2px solid #ded4c2;padding-left:28px}.next b{color:#5d5d2a}
</style><main><h1>任务一：tFNA目标皮肤层递送潜力评估</h1><div class="subtitle">探索性运输建模 · 活性表皮与浅真皮为共同目标区域 · 载体结合态 CK 当量</div><div class="steps">${stages.map(([a,b],i)=>`<div class="step"><strong>${i+1}　${a}</strong><span>${b}</span></div>`).join('')}</div><div class="grid">${cards.join('')}</div><footer><div><strong>运输潜力支持继续验证，候选选择取决于实测条件</strong><p>tFNA 与 NLC 的目标层合计保留接近；装载、稳定性及直接 CK 递送实验决定后续投入。</p></div><div class="next"><b>优先实验</b>　早期 CK 绝对进入量 → VE / 真皮时间分布 → 载体完整性<br><b>图像说明</b>　A 为模型示意；B—F 直接嵌入本项目计算图原文件。</div></footer></main></html>`;
await fs.writeFile(path.join(out,'任务一_目标层递送流程图.html'),html,'utf8');
const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
try{
 const page=await browser.newPage({viewport:{width:3000,height:2000},deviceScaleFactor:2});
 await page.setContent(html,{waitUntil:'load'});await page.evaluate(()=>document.fonts.ready);
 const failures=await page.locator('img').evaluateAll(imgs=>imgs.filter(i=>!i.complete||!i.naturalWidth).length);
 if(failures)throw Error('Image load failure');
 const overflow=await page.locator('.card').evaluateAll(els=>els.filter(e=>e.scrollHeight>e.clientHeight+2||e.scrollWidth>e.clientWidth+2).length);
 if(overflow)throw Error('Diagram content overflow: '+overflow);
 await page.locator('main').screenshot({path:path.join(out,'任务一_目标层递送流程图.png')});
 console.log('Flowchart saved with five original scientific images.');
}finally{await browser.close()}
