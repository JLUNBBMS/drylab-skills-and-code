import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const root=path.dirname(fileURLToPath(import.meta.url));
const dest=path.join(root,'output/task1_evidence_and_results.xlsx');
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(dest));
const blocks=JSON.parse(await fs.readFile(path.join(root,'results/workbook_data.json'),'utf8'));
const existing=new Set(JSON.parse(await fs.readFile(path.join(root,'results/workbook_sheets.json'),'utf8')));
for(const b of blocks){
  if(!existing.has(b.sheet)){
    const s=wb.worksheets.add(b.sheet);existing.add(b.sheet);
    s.showGridLines=false;
    s.getRange('A1:M24').format.font={name:'Arial',size:10};
    s.getRange('A1:M24').format.columnWidth=18;
    s.getRange('A1:M24').format.wrapText=true;
    s.getRange('A1:M1').merge();s.getRange('A1').values=[[b.title]];
    s.getRange('A1:M1').format={fill:'#5d5d2a',font:{color:'#FFFFFF',bold:true,size:16},rowHeight:34};
    s.getRange('A2:M2').merge();s.getRange('A2').values=[[b.note]];s.getRange('A2:M2').format.rowHeight=42;
  }
  const s=wb.worksheets.getItem(b.sheet);
  s.getRangeByIndexes(b.row-1,0,b.matrix.length,b.matrix[0].length).values=b.matrix;
  if(b.title || b.row>8){
    s.getRangeByIndexes(b.row-1,0,1,b.matrix[0].length).format={fill:'#7e0909',font:{color:'#FFFFFF',bold:true},wrapText:true,rowHeight:48};
    s.getRangeByIndexes(b.row,0,b.matrix.length-1,b.matrix[0].length).format.rowHeight=42;
  }
}
const overview=wb.worksheets.getItem('Overview');
overview.getRange('A1').values=[['Task 1 target-layer delivery assessment']];
overview.getRange('B4').values=[['VE + dermis, 24 h']];overview.getRange('F4').values=[['Top frequency']];
for(let r=5;r<=8;r++)overview.getRange(`B${r}`).formulas=[[`='Baseline 24h'!L${r}`]];
overview.getRange('A11').values=[['tFNA and NLC have similar baseline target retention; tFNA has greater dermal retention.']];
overview.getRange('A12').values=[['Scenario intervals describe assumed parameter ranges; all six paired intervals cross zero.']];
overview.getRange('A13').values=[['Priority measurements: early CK entry, VE/dermis absolute mass and carrier integrity.']];
overview.getRange('A23').values=[['Primary: VE + dermis retention (ug/cm2). Human-assisted calibration and decision conditions are separate scenarios.']];
const testsBlock=blocks.find(b=>b.sheet==='Numerical Tests');
wb.worksheets.getItem('Numerical Tests').getRange('E5:E22').values=testsBlock.matrix.slice(1).map(r=>[r[4]?1:0]);
wb.worksheets.getItem('Numerical Tests').getRange('E4').values=[['passed (1=yes)']];
const auditBlock=blocks.find(b=>b.sheet==='Scope Gate' && b.row===17);
wb.worksheets.getItem('Scope Gate').getRange('B18:B27').values=auditBlock.matrix.slice(1).map(r=>[r[1]?1:0]);
wb.worksheets.getItem('Scope Gate').getRange('B17').values=[['passed (1=yes)']];
overview.getRange('B18').formulas=[["=COUNTIF('Numerical Tests'!E5:E22,1)"]];
overview.getRange('B20').formulas=[["=COUNTIF('Scope Gate'!B18:B27,1)"]];
const baseline=wb.worksheets.getItem('Baseline 24h');
baseline.getRange('A2').values=[['Primary endpoint: viable epidermis plus dermis retained mass at 24 h; sink is reported separately.']];
baseline.getRange('L4:L8').copyFrom(baseline.getRange('K4:K8'),'all');
baseline.getRange('L4').values=[['target_retention_ug_cm2']];
baseline.getRange('L4:L8').format.columnWidth=25;
baseline.getRange('L4').format.wrapText=true;
baseline.getRange('L4').format={fill:'#7e0909',font:{color:'#FFFFFF',bold:true},wrapText:true};
for(let r=5;r<=8;r++)baseline.getRange(`L${r}`).formulas=[[`=E${r}+G${r}`]];
baseline.getRange('L5:L8').setNumberFormat('0.0000');
wb.worksheets.getItem('Uncertainty Summary').getRange('B4').values=[['median_target_retention_ug_cm2']];
wb.worksheets.getItem('Uncertainty Summary').getRange('B4').format.wrapText=true;
wb.worksheets.getItem('Uncertainty Summary').getRange('A2').values=[['Primary outcome: VE + dermis retained mass; central 95% scenario intervals, 256 paired sets.']];
wb.worksheets.getItem('Grid Convergence').getRange('F4').values=[['target_retention_ug_cm2']];
for(const name of ['Human Transfer','Boundary Conditions','Decision Conditions']){
 const s=wb.worksheets.getItem(name);const range=s.getUsedRange();
 range.setNumberFormat('0.0000');
}
wb.worksheets.getItem('Human Transfer').getRange('C5:C6').setNumberFormat('0.000E+00');
wb.worksheets.getItem('Human Transfer').getRange('B11:B15').setNumberFormat('0.000E+00');
wb.worksheets.getItem('Boundary Conditions').getRange('C5:C10').setNumberFormat('0.000E+00');
wb.worksheets.getItem('Boundary Conditions').getRange('C16:C21').setNumberFormat('0.000E+00');
const raw=wb.worksheets.getItem('Uncertainty Raw');
raw.getRange('AD4:AD1028').copyFrom(raw.getRange('AC4:AC1028'),'all');
raw.getRange('AD4').values=[['target_retention_ug_cm2']];
raw.getRange('AD4').format={fill:'#7e0909',font:{color:'#FFFFFF',bold:true},wrapText:true};
raw.getRange('AD4:AD1028').format.columnWidth=25;
const rawBlock=blocks.find(b=>b.sheet==='Uncertainty Raw');
raw.getRange('AD5:AD1028').values=rawBlock.matrix.slice(1).map(row=>[row.at(-1)]);
raw.getRange('AD5:AD1028').setNumberFormat('0.0000');
console.log((await wb.inspect({kind:'table',range:'Overview!A4:F8',include:'values,formulas',tableMaxRows:5,tableMaxCols:6,maxChars:2000})).ndjson);
console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!',options:{useRegex:true,maxResults:10},maxChars:1000})).ndjson);
const previews=path.join(root,'output/spreadsheet_renders');
let index=0;
for(const name of existing){
 const s=wb.worksheets.getItem(name);
 const b=blocks.find(b=>b.sheet===name);
 const n=b?.title ? 13 : Math.min(b?.matrix[0].length || 6,13);
 const col=String.fromCharCode(64+n);
 const preview=await wb.render({sheetName:name,range:`A1:${col}${name==='Overview'?23:Math.min((b?.matrix.length || 10)+3,16)}`,scale:1});
 const filename=`${String(++index).padStart(2,'0')}_${name.replaceAll(' ','_')}.png`;
 await fs.writeFile(path.join(previews,filename),new Uint8Array(await preview.arrayBuffer()));
}
await (await SpreadsheetFile.exportXlsx(wb)).save(dest);
console.log('Workbook saved');
