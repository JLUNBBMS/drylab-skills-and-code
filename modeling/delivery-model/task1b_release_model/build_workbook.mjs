import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';
const root=path.dirname(fileURLToPath(import.meta.url));
const output=path.join(root,'outputs','task1b_20260914');
const data=JSON.parse(await fs.readFile(path.join(output,'workbook_content.json'),'utf8'));
const wb=Workbook.create();
const names=['填写说明','配料换算','批次信息','原始观测','终点回收','证据来源'];
const sheets=Object.fromEntries(names.map(n=>[n,wb.worksheets.add(n)]));
function col(i){let s='';for(i++;i;i=Math.floor((i-1)/26))s=String.fromCharCode(65+(i-1)%26)+s;return s;}
function table(name,rows,widths){
 const s=sheets[name],last=col(rows[0].length-1),n=rows.length;
 s.getRange(`A1:${last}${n}`).values=rows;
 s.getRange(`A1:${last}${n}`).format.font={name:'Arial',size:10,color:'#222D36'};
 s.getRange(`A1:${last}${n}`).format.rowHeight=32;
 s.getRange(`A1:${last}${n}`).format.wrapText=true;
 s.getRange(`A1:${last}${n}`).format.verticalAlignment='center';
 s.getRange(`A1:${last}1`).format={fill:'#344A5F',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},rowHeight:58,wrapText:true};
 widths.forEach((v,i)=>s.getRange(`${col(i)}1:${col(i)}${n}`).format.columnWidth=v);
 s.freezePanes.freezeRows(1);s.showGridLines=false;
 return s;
}
table('填写说明',[
 ['项目','操作与定义'],
 ['研究问题','固定 tFNA–CK 装载条件，比较加入不同量寡聚人参多糖后的 CK 释放。'],
 ['当前结论','尚无本体系实测曲线；本工作簿不含最佳比例或模拟实测值。'],
 ['填写顺序','先确认原料和方法，再填写批次信息、原始观测及终点回收。黄色为待填数据。'],
 ['配比定义','多糖干基有效质量 / CK 实际质量，mg/mg；0∶1 是不加多糖的 tFNA–CK。'],
 ['实验矩阵','6 个主配方 × 3 个独立制备批次 × 8 个取样时间，144 条观测记录。'],
 ['独立批次','B1–B3 对应三次独立 tFNA–CK 制备；同批分装到各比例组。重复进样不增加批次数。'],
 ['额外方法对照','已溶解 CK 膜通过、基质空白、必要时空载 tFNA 加游离 CK；不计入 18 条主曲线。'],
 ['原始观测列 A–F','数据类型、曲线编号、批次、配方、质量比和时间已预填，保持编号可追溯。'],
 ['initial_ck_ug','初始实测总 CK，μg；包含测得的未结合 CK，不用投料量代替。'],
 ['initial_receiver_volume_ml','初始受体介质体积，mL；同一曲线各行填写同一个初始值。'],
 ['receiver_ck_ug_ml','取样前受体 CK 浓度，μg/mL；填写已校正检测稀释倍数的数值。'],
 ['withdrawn_ml / replaced_ml','当次移出体积 / 补入不含 CK 介质体积，mL；未取样时填 0，不留空。'],
 ['原始观测列 L–O','公式计算取样前体积、此前已取出 CK、累计转移质量和分数；按曲线连续时间顺序填写。'],
 ['终点回收','测供体残留与膜/容器表面回收 CK；不在此重复填写末次受体样品。程序计算总回收率。'],
 ['定性输入','析出填 yes/no；载体完整性可接受填 yes/no。未知请留空，不能直接视为通过。'],
 ['方法适用范围','取样前充分混匀，补液不含 CK，无未记录的蒸发或损失。低聚糖/载体过膜须独立检查。'],
 ['配料换算','仅将已选浓度换算为质量，不代表装载可行、可溶或推荐剂量。实际记录以分析测量为准。'],
 ['分析入口','将填写后的工作簿另存，交给 task1B 分析程序；原始列名不可改名。'],
 ['推荐条件','需方法验证记录、预先确定的释放指标及匹配的 0∶1 对照；满足条件后也仅是待新批次验证候选。'],
 ['范围限制','不由此工作簿直接推断皮肤透过、细胞内暴露、协同或人体护肤持续时间。']
],[34,108]);
sheets['填写说明'].getRange('A2:B21').format.rowHeight=42;

const mix=sheets['配料换算'];
table('配料换算',[
 ['项目','输入值','单位或说明','','',''],
 ['换算范围',null,'输入均为拟制备配方条件，需先确认装载和溶解可行性。','','',''],
 ['CK 最终浓度',null,'μg/mL','','',''],
 ['配方终体积',null,'mL','','',''],
 ['tFNA 最终浓度',null,'nM；需独立确认与 CK 装载条件匹配。','','',''],
 ['原料干基有效糖含量',null,'质量分数，0–1；不是用百分数数值 95 表示 95%。','','',''],
 ['原料水分',null,'质量分数，0–1；无水干粉填 0。','','',''],
 ['固定条件',null,'tFNA、CK、溶剂和基质保持一致，只改变多糖质量。','','',''],
 ['计算说明',null,'称量质量 = 有效糖质量 / [干基有效含量 × (1 − 水分)]。','','',''],
 ['配方','多糖∶CK（mg/mg）','CK 质量（mg）','有效多糖（mg）','原料称量（mg）','tFNA 总量（pmol）'],
 ...data.ratios.map(r=>[`R${r}`,r,null,null,null,null])
],[30,23,42,24,24,25]);
mix.getRange('A10:F10').format={fill:'#344A5F',font:{color:'#FFFFFF',bold:true},wrapText:true,rowHeight:42};
mix.getRange('B3:B7').format.fill='#FFF2CC';
mix.getRange('B6:B7').setNumberFormat('0.0%');
for(let r=11;r<=16;r++){
 mix.getRange(`C${r}`).formulas=[[`=IF(COUNT($B$3:$B$4)<2,"",IF(OR($B$3<=0,$B$4<=0),"输入须大于0",$B$3*$B$4/1000))`]];
 mix.getRange(`D${r}`).formulas=[[`=IF(ISNUMBER(C${r}),B${r}*C${r},"")`]];
 mix.getRange(`E${r}`).formulas=[[`=IF(COUNT(D${r},$B$6,$B$7)<3,"",IF(OR($B$6<=0,$B$6>1,$B$7<0,$B$7>=1),"含量或水分无效",D${r}/($B$6*(1-$B$7))))`]];
 mix.getRange(`F${r}`).formulas=[[`=IF(COUNT($B$4:$B$5)<2,"",IF(OR($B$4<=0,$B$5<=0),"输入须大于0",$B$4*$B$5))`]];
}
mix.getRange('C11:F16').setNumberFormat('0.000');
const metaKeys=Object.keys(data.design[0]);
table('批次信息',[metaKeys,...data.design.map(r=>metaKeys.map(k=>r[k]))],[20,14,18,23,18,20,16,22,26,36,32,40,18,45]);
sheets['批次信息'].getRange('E2:N19').format.fill='#FFF2CC';
const s=table('原始观测',[[...data.raw_columns,'receiver_volume_before_ml','previous_removed_ck_ug','cumulative_transferred_ck_ug','fraction_initial_ck'],
 ...data.raw.map(r=>[...r,null,null,null,null])],Array(15).fill(20));
s.getRange('G2:K145').format.fill='#FFF2CC';
s.getRange('L2:O145').format.fill='#EEF2F5';
s.getRange('E2:N145').setNumberFormat('0.000');s.getRange('O2:O145').setNumberFormat('0.0%');
for(let r=2;r<=145;r++){
 const start=(r-2)%8===0;
 s.getRange(`L${r}`).formulas=[[start?`=IF(ISNUMBER(H${r}),H${r},"")`:`=IF(COUNT(L${r-1},J${r-1},K${r-1})<3,"",L${r-1}-J${r-1}+K${r-1})`]];
 s.getRange(`M${r}`).formulas=[[start?'=0':`=IF(COUNT(M${r-1},I${r-1},J${r-1})<3,"",M${r-1}+I${r-1}*J${r-1})`]];
 s.getRange(`N${r}`).formulas=[[`=IF(COUNT(L${r},M${r},I${r})<3,"",L${r}*I${r}+M${r})`]];
 s.getRange(`O${r}`).formulas=[[`=IF(COUNT(N${r},G${r})<2,"",IF(G${r}<=0,"CK质量须大于0",N${r}/G${r}))`]];
}
table('终点回收',[data.end_columns,...data.end],[22,26,28,27,30,65]);
sheets['终点回收'].getRange('B2:F19').format.fill='#FFF2CC';
sheets['终点回收'].getRange('D2:E19').dataValidation={rule:{type:'list',values:['yes','no']}};
const ek=['id','topic','source','level','supports','limit','url'];
table('证据来源',[['编号','主题','原始来源','已核查层级','可支持的用途','不能外推的部分','链接'],...data.evidence.map(r=>ek.map(k=>r[k]))],[10,25,65,38,55,66,70]);
sheets['证据来源'].getRange('A2:G7').format.rowHeight=76;

// Authoring-only formula checks; test values removed before final export.
mix.getRange('B3:B7').values=[[100],[2],[250],[.8],[.1]];
let example=mix.getRange('C15:F15').values[0];
if(Math.abs(example[0]-.2)>1e-8||Math.abs(example[1]-1)>1e-8||Math.abs(example[2]-1/.72)>1e-8||Math.abs(example[3]-500)>1e-8)throw new Error('Mix formula regression '+JSON.stringify(example));
mix.getRange('B3:B7').clear({applyTo:'contents'});
s.getRange('G2:K5').values=[[100,10,0,0,0],[100,10,1,1,1],[100,10,2,1,0],[100,10,3,0,0]];
const q=s.getRange('N2:N5').values.map(x=>x[0]);
if(q.some((x,i)=>Math.abs(x-[0,10,21,30][i])>1e-8))throw new Error('Sampling formula regression '+JSON.stringify(q));
s.getRange('G2:K5').clear({applyTo:'contents'});
const scan=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:30},summary:'final formula error scan'});
await fs.writeFile(path.join(output,'workbook_formula_check.ndjson'),scan.ndjson);
await fs.writeFile(path.join(output,'workbook_ranges.ndjson'),(await wb.inspect({kind:'table',range:'配料换算!A10:F16',include:'values,formulas',tableMaxRows:8,tableMaxCols:6})).ndjson);
const previews=[['填写说明','A1:B12'],['配料换算','A1:F16'],['批次信息','A1:G7'],['批次信息','H1:N7'],['原始观测','A1:H10'],['原始观测','I1:O10'],['终点回收','A1:F7'],['证据来源','A1:D7'],['证据来源','E1:G7']];
for(let i=0;i<previews.length;i++){
 const [sheetName,range]=previews[i];const blob=await wb.render({sheetName,range,scale:1.3,format:'png'});
 await fs.writeFile(path.join(output,`preview_${i+1}.png`),new Uint8Array(await blob.arrayBuffer()));
}
const file=await SpreadsheetFile.exportXlsx(wb);await file.save(path.join(output,'task1B_配比实验与释放记录.xlsx'));
console.log('Workbook exported; formula regressions passed. '+scan.ndjson);
