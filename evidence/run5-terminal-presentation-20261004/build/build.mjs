import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { Presentation, PresentationFile, FileBlob } from '@oai/artifact-tool';
const workspaceDir=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const SKILL_DIR='/Users/frank/.codex/plugins/cache/openai-primary-runtime/presentations/26.905.11957/skills/presentations';
const RUNTIME_PYTHON='/Users/frank/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3';
const {resolvePresentationFont,finalizePresentation}=await import(pathToFileURL(path.join(SKILL_DIR,'container_tools/artifact_tool_utils.mjs')).href);
const font=resolvePresentationFont({fontFamily:'Helvetica Neue'});
const presentation=Presentation.create({slideSize:{width:1280,height:720}});
const C={navy:'#102D32',paper:'#F5F3EC',ink:'#152E32',muted:'#506368',teal:'#157A6E',amber:'#9B5B1A',white:'#FFFFFF',line:'#D1DAD5'};
const F='/Users/frank/mygit/Tablekeeper/factory';
const O='/Users/frank/mygit/Tablekeeper/runs/run5-preparation-20261004';
const GH='https://github.com/Xuefeng-Zhu/Tablekeeper-factory/tree/main/evidence/';
const transcript=[];
function text(slide,name,value,x,y,w,h,size=28,color=C.ink,bold=false){
 const s=slide.shapes.add({geometry:'textbox',name,position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
 s.text=value;s.text.style={typeface:font,fontSize:size,color,bold,autoFit:'none',verticalAlignment:'top',insets:{top:0,right:0,bottom:0,left:0}};
 return s;
}
function slide(title,number,dark=false){
 const s=presentation.slides.add();s.background.fill=dark?C.navy:C.paper;
 if(title)text(s,'title',title,64,55,1152,105,46,dark?C.white:C.ink,true);
 text(s,'draft-footer',`DRAFT / 04 Oct 2026 23:46 UTC / ${String(number).padStart(2,'0')}`,64,675,1152,24,17,dark?'#BDCECA':C.muted);
 return s;
}
function notes(s,title,body,sources){
 const value=`AI-assisted factual draft for participant review. Evidence scope: 2026-10-04 23:46 UTC, including the package check ending 23:46:12.484363Z. Final product candidate 3329a823 is rejected, no stage accepted, and workers are stopped. Public release and final submission are not established.\n\n${title}\n${body}\n\nSources\n${sources.join('\n')}\n\nPrivate source links may require repository access. This presentation is not room-video evidence.`;
 s.speakerNotes.textFrame.setText(value);transcript.push({title,notes:value,sources});
}
function table(s,name,values,y,widths,heights,size=25){
 const t=s.tables.add({rows:values.length,columns:values[0].length,left:64,top:y,width:1152,height:heights.reduce((a,b)=>a+b,0),columnWidths:widths,values});
 t.styleOptions={headerRow:false,bandedRows:false};
 t.borders.assign({fill:C.line,width:1,style:'solid'});
 for(let r=0;r<values.length;r++){
  t.rows[r].height=heights[r];
  for(let c=0;c<values[r].length;c++){
   const cell=t.getCell(r,c);cell.fill=r===0?C.navy:C.paper;
   cell.text.style={typeface:font,fontSize:size,color:r===0?C.white:C.ink,bold:r===0,autoFit:'none',verticalAlignment:'middle',insets:{left:15,right:15,top:12,bottom:12}};
  }
 }
 return t;
}
{
 const s=slide('',1,true);
 text(s,'team','MillieMoon',64,58,1150,88,72,C.white,true);
 text(s,'subject','Tablekeeper / Run 5 outcome',64,154,1150,64,48,'#B8DAD0',false);
 text(s,'objective','Seven BAND seats configured for four stages.\nOutcome: 0 accepted; Stages 2–4 unimplemented.',64,267,1090,94,32,C.white);
 text(s,'seven','7',64,397,100,119,100,'#B8DAD0',true);
 text(s,'registered','registered roles',178,439,420,46,29,C.white);
 text(s,'one','1',714,397,100,119,100,'#B8DAD0',true);
 text(s,'active','active model seat at a time',826,425,388,90,29,C.white);
 text(s,'roles','PM / Architect / Designer / Backend / Frontend / QA / Reviewer',64,551,1152,39,25,C.white);
 text(s,'runtime','All seven configured with Codex 0.160.0 / gpt-6-astra. BAND SDK 4.0.0.',64,602,1152,38,23,'#BDCECA');
 notes(s,'Factory objective and terminal outcome','Seven separate identities were configured. This does not imply seven material product contributors; Designer and Frontend have no completed later-stage product work. One active model turn limits shared-checkout write conflicts. Effort is medium except Architect, QA and Reviewer high. One all-stage dispatch occurred at 2026-10-04T21:06:55.943682Z in room 12cde259-0fcd-4551-84c7-52c443cb5600. The terminal product disposition is STOP/REPLAN after three repairs, not four-stage completion. Application attempts share the private canonical Tablekeeper repository on independent branches; this attempt is run-5, factory tools separate.',[`${O}/packaging/FACTORY.draft.md`,`${F}/evidence/run5-launch-20261004/launch/dispatch-verification.json`,'https://github.com/Xuefeng-Zhu/Tablekeeper/tree/run-5',`${GH}run5-terminal-closure-20261004`]);
}
{
 const s=slide('Complete handoffs led to a recorded stop',2);
 const steps=[['1  Assignment','PM sends full requirements,\nrevision, owner and limits.'],['2  Receipt','The peer checks every part\nand acknowledges its digest.'],['3  Candidate','The owner returns a commit\nwith commands and results.'],['4  Release gate','Reviewer rejects; PM records\nSTOP at the repair limit.']];
 steps.forEach(([head,body],i)=>{text(s,`step-${i}`,head,64,176+i*112,314,35,26,C.teal,true);text(s,`step-body-${i}`,body,64,215+i*112,314,67,23);});
 s.images.add({blob:new Uint8Array(await fs.readFile(path.join(workspaceDir,'assets/terminal-outcome.jpg'))),contentType:'image/jpeg',fit:'contain',position:{left:400,top:190,width:816,height:382},alt:'Actual Run 5 BAND room showing the PM final rejection, exhausted 3/3 repair limit and stop decision. Genuine screenshot saved 23:36 UTC.'});
 text(s,'still-caption','Real Run 5 room: PM rejection and stop at 23:29 UTC.\nScreenshot saved 23:36 UTC; this is not a video.',400,596,816,63,21,C.muted);
 notes(s,'Recorded stop and real room still','The original terminal-outcome.jpg is preserved byte-for-byte and shown uncropped. SHA-256 787944ce9efe0e6a9baad772decc2a38a4850c3e8295d6ad2e0a924eb7e93832, 157457 bytes. Provenance saved_at 2026-10-04T23:36:19.173495Z. Visible PM handoff ACK f735f446-38ec-4b2d-9659-ed0bff32497c, team stop 493ace48-7d8b-469d-ad82-6fb063e05a0f, and public final fe9e5ec6-69c5-4871-868f-284fdf84cceb at 23:29:24.626626Z. The screenshot shows Docker checks blocked at that assigned gate; later operator verification is separately explained on slide 5. A receipt proves complete transport, not correct implementation. The still is not video or a fabricated playback.',[`${O}/packaging/media/terminal-outcome.provenance.json`,`${F}/evidence/run5-terminal-closure-20261004/media/terminal-outcome.jpg`,`${F}/mandates/factory-pm.md`,`${F}/mandates/factory-reviewer.md`,`${GH}run5-terminal-closure-20261004`]);
}
{
 const s=slide('Stage 1 rejected after the final repair',3);
 text(s,'subtitle','Independent gate / exact candidate 3329a823 / repair 3 of 3',64,147,1152,40,27,C.amber);
 table(s,'terminal-findings',[
 ['Finding','Final independent review'],
 ['Fixture numeric error handling','Closed in observed host checks'],
 ['Very large fixture integers','Closed in observed host checks'],
 ['Historical receipt consistency','Still accepts contradictions on import']
 ],220,[560,592],[54,82,82,91],25);
 text(s,'candidate','Rejected 3329a823 / record-only closeout 350e3d9',64,565,1152,45,29,C.amber,true);
 text(s,'progress','Repairs 3/3 exhausted. No accepted stage or Stage 2–4 implementation.',64,622,1152,39,24,C.muted);
 notes(s,'Exact terminal product decision','Independent Reviewer final at 23:26:43 UTC rejects candidate 3329a8238ece53e06812cce4b5c6222476dd33ab. Record-only closeout 350e3d95855a7b10eacafd59fca67ffaf48a348e preserves Stage 1 tree 13192852a7341f8d7e6b2bc6076c9e59cfa3843b. A create receipt with request party_size 2 still imports a contradictory response 3; a batch move requesting table z still imports a historical response table t. Both replace destination and replay altered responses instead of rejecting invalid import. Related historical local/absolute time and duration contradictions also remain. This compares each request with its own historical response, not current amended bookings. Original receipt shape/identity cases closed but the broader family did not. Reviewer host results: original repro 58/58 (three old conditional assertions no longer execute), 11/11 baseline groups, two injected mechanism groups; extended 125 PASS/6 FAIL; direct pair confirmation 2 PASS/4 FAIL. These overlap and are not one combined score. All product repairs are exhausted; no fourth repair or later-stage advance follows from unused budget or green samples.',[`${O}/packaging/presentation/assets/gate-stage-1-final-review.md`,'https://github.com/Xuefeng-Zhu/Tablekeeper/blob/350e3d95855a7b10eacafd59fca67ffaf48a348e/records/stage-1-stop.md','https://github.com/Xuefeng-Zhu/Tablekeeper/blob/350e3d95855a7b10eacafd59fca67ffaf48a348e/records/gate-stage-1-final-review.md']);
}
{
 const s=slide('Two operator infrastructure interventions',4);
 text(s,'subtitle','The run includes human infrastructure work after dispatch.',64,147,1152,42,28,C.amber,true);
 table(s,'resource-timeline',[
 ['UTC','Global VM cap','Observed action'],
 ['22:07','1,024 MiB','Architecture review container exits after an out-of-memory kill.'],
 ['22:31','4,096 MiB','Operator restarts OrbStack and restores the same two containers.'],
 ['22:49','2,048 MiB','User requests the lower cap. Operator restarts and restores again.']
 ],214,[165,220,767],[54,88,88,88],24);
 text(s,'resource-warning','The current 2 GiB global cap also covers VM and daemon overhead.',64,578,1152,40,28,C.amber,true);
 text(s,'autonomy-limit','State continuity remains unverified. Fully autonomous execution is not claimed.',64,624,1152,38,23,C.muted);
 notes(s,'OOM and both operator interventions','At 22:07:51.903833782Z the architecture review container was OOM-killed under a 1024 MiB global OrbStack ceiling despite a 2 GiB per-container setting. Docker responsiveness recovered before the first operator restart. At 22:30 the operator set 4096 MiB and activated it with one stop/start at 22:31:18–22:31:24; the same two verified original containers were restored. At the user request, a second stop/start at 22:49:06–22:49:11 activated 2048 MiB and restored those IDs. Docker then reported 2073866240 bytes total VM memory. Both interrupted containers; state/session continuity was not tested. VM overhead means this global cap is not itself proof of a full 2 GiB application allowance. No operator product code edits or BAND instructions accompanied these actions. After the terminal run, the two Backend-owned test containers were stopped at 23:37 without deletion or VM setting changes; later supplied-suite verification did not erase the interventions or establish full resource/performance conformance.',[`${F}/evidence/run5-orbstack-memory-repair-20261004/README.md`,`${F}/evidence/run5-user-2g-cap-20261004/orbstack-user-2g-cap.json`,`${F}/evidence/run5-terminal-closure-20261004/owned-test-containers-stopped.json`,`${GH}run5-orbstack-memory-repair-20261004`,`${GH}run5-user-2g-cap-20261004`]);
}
{
 const s=slide('120/120 supplied checks passed after the stop',5);
 text(s,'subtitle','Post-run operator verification / unchanged Stage 1 product tree',64,147,1152,40,27,C.teal);
 table(s,'postrun-evidence',[
 ['Evidence','Result','Verified scope'],
 ['Stage 1 isolated suite','120 collected / 120 passed','Supplied checks on clean closeout 350e3d9.'],
 ['Stage 2 probe','25 collected / 0 passed','First failure stops probe; no folder or credit.'],
 ['Offline package check','Exit 0 at 23:46 UTC','Layout, room, mandates and credential patterns.']
 ],213,[310,315,527],[54,93,93,93],24);
 text(s,'environment','Isolated run: 23:38 UTC, under the existing 2 GiB global VM cap.',64,581,1152,39,25,C.teal,true);
 text(s,'gate-limit','The receipt defects and independent rejection remain. The four-stage goal is incomplete.',64,626,1152,37,23,C.amber);
 notes(s,'Post-run official isolated and offline package evidence','After worker shutdown, operator fresh clone at closeout 350e3d95855a7b10eacafd59fca67ffaf48a348e remained clean, exact Stage 1 tree 13192852a7341f8d7e6b2bc6076c9e59cfa3843b unchanged. Official command python -m harness run --track tablekeeper --repo <fresh clone> --all --mode isolated ran 23:38:15.483787–23:38:56.297110 UTC, exit 0, user OrbStack memory 2048 MiB unchanged. Stage 1 report: 120 collected, 120 passed, 0 failed/errors/skipped/deselected; summary contains only folder 1. Automatic Stage 2 overshoot probe collected 25, passed 0, failed 1 and stopped; no Stage 2 source folder or credit. The harness highest_contiguous 1 describes supplied checks only; independent accepted-stage count remains zero. This is new operator evidence, separate from the assigned gate historical Docker blocker. It does not cover the independently demonstrated import contradictions or broader heavy-state/resource/latency requirements. A subsequent offline harness check of the metadata package ran 23:46:11.992480–23:46:12.484363 UTC, exit 0; staged root tree 3853266bd4829ab423a534ff942151a1ff871be8 and product tree unchanged. That check covers layout/room/mandates/credential patterns, not product acceptance or publication. A final package Git push or submission is not claimed here.',[`${F}/evidence/run5-postrun-isolated-20261004/isolated-command.json`,`${F}/evidence/run5-postrun-isolated-20261004/isolated-all/stage-1/report.json`,`${F}/evidence/run5-postrun-isolated-20261004/isolated-all/summary.json`,`${O}/packaging/presentation/assets/package-check.json`,`${GH}run5-postrun-isolated-20261004`]);
}
{
 const s=slide('Run closed; submission evidence preserved',6);
 text(s,'tokens','75,831,611',64,170,590,85,61,C.teal,true);
 text(s,'token-label','reported tokens, including 74,291,200 cached input\n(~98% of total); not dollars or account quota',64,268,590,83,24,C.muted);
 text(s,'elapsed','2h 22m 29s',64,386,590,62,43,C.teal,true);
 text(s,'time-label','Dispatch to PM final. Workers stopped at 23:33 UTC.\nNo owned parent or child worker remained.',64,457,590,65,23,C.muted);
 text(s,'room','Genuine full-session export',712,180,504,46,31,C.teal,true);
 text(s,'room-detail','4,602 unique events\n1 human text: the initial dispatch\nPM terminal report included',712,243,504,112,26);
 text(s,'privacy','Bounded privacy review complete.\nSupports unchanged private preservation.',712,385,504,68,24,C.muted);
 text(s,'publication','Package check passed. Public release\nand final submission are not established.',712,476,504,61,23,C.muted);
 text(s,'video','Video explicitly deferred by participant. This deck is a draft.',64,577,1152,46,29,C.amber,true);
 text(s,'authorship','AI-assisted factual narrative; participant review and authorship resolution required.',64,632,1152,32,22,C.muted);
 notes(s,'Final accounting, export and remaining submission limits','Authoritative factory ledger: Run 5 reported tokens 75831611, including input 75633435 (74291200 cached, 1342235 uncached) and output 198176. Cached input is about 97.9686% of reported total; do not add it again. Reasoning output is already a subset of output. Cumulative final total 221514710 equals baseline 145683099 plus Run 5. Pinned BAND SDK display mapping differs; use the reconciled factory ledger, not an additional sum of displayed counters. No USD or ChatGPT quota conversion is available. Dispatch 21:06:55.943682 to PM final 23:29:24.626626 = 8548.682944 seconds, rounded on slide to 2h22m29s; through stop at23:33:07.598829 = 8771.655147 seconds. All seven contexts drained; no owned parent/children alive after stop. Ledger unchanged before/after, SHA13631cb7cde562f45029c659cff613fc5f61c1d256bb77717dc41ecfbf2394f2. Exported23:33:31.490Z, full scope room12cde259-0fcd-4551-84c7-52c443cb5600, 7505750 bytes, SHA c934ff785a565d1198a12c9a806217897217046f317dc9ef961730a647ef3e3e, 4602 unique events and195 text events. Exactly one User text is original dispatch d5861cdd-0b57-4393-a97f-0dfb9201cec2; PM final present. Bounded privacy review at23:39:52.891765Z found no actionable keys/JWT/private-key/cookie/unclassified credential values; other matches were public fixtures/synthetic tests/prose. Private preservation only, not exhaustive absence proof or public-release approval. Participant deferred genuine room video; a still/deck does not replace it. No public release, final submission or human-authorship claim is made. The full four-stage product and required UI remain incomplete.',[`${F}/evidence/run5-terminal-closure-20261004/final-accounting.json`,`${F}/evidence/run5-terminal-closure-20261004/closure-receipt.json`,`${F}/evidence/run5-terminal-closure-20261004/room-download-receipt.json`,`${F}/evidence/run5-terminal-closure-20261004/room-privacy-review.json`,`${GH}run5-terminal-closure-20261004`]);
}
await fs.writeFile(path.join(workspaceDir,'deck-source.json'),JSON.stringify({title:'MillieMoon Tablekeeper Factory Run 5 — Terminal outcome',status:'AI_ASSISTED_DRAFT_REVIEW_REQUIRED',snapshot_utc:'2026-10-04T23:46Z',snapshot_precision:'minute; includes offline package check ending 23:46:12.484363Z',authoring:'AI-assisted factual draft for participant review',font,slides:transcript},null,2)+'\n');
await fs.writeFile(path.join(workspaceDir,'build/presentation.json'),JSON.stringify(presentation.toProto()));
const candidatePath=path.join(workspaceDir,'build/candidate-2346-r4.pptx');
await (await PresentationFile.exportPptx(presentation)).save(candidatePath);
const result=await finalizePresentation({explicitTotalSlideCount:6,requiredNativeTableOwnerSlides:[3,4,5],requiredNativeChartOwnerSlides:[],workspaceDir,candidatePath,finalPath:path.join(workspaceDir,'output/MillieMoon-Tablekeeper-Run5-DRAFT-2346-r4.pptx'),pythonExecutable:RUNTIME_PYTHON,integrityValidatorPath:path.join(SKILL_DIR,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(SKILL_DIR,'container_tools/inspect_presentation_layout_geometry.py'),layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-heading-fit','--require-native-table-slide','3','--require-native-table-slide','4','--require-native-table-slide','5'],fontPolicy:{basis:'design',families:[font]},verifyArtifactToolImport:true,receiptPath:path.join(workspaceDir,'build/validation-2346-r4.json')});
console.log(JSON.stringify(result));
const final=await PresentationFile.importPptx(await FileBlob.load(path.join(workspaceDir,'output/MillieMoon-Tablekeeper-Run5-DRAFT-2346-r4.pptx')));
for(let i=0;i<final.slides.items.length;i++){
 const s=final.slides.items[i];
 const png=await final.export({slide:s,format:'png',scale:1});
 await fs.writeFile(path.join(workspaceDir,`previews/r4-slide-${i+1}.png`),new Uint8Array(await png.arrayBuffer()));
 const layout=await s.export({format:'layout'});await fs.writeFile(path.join(workspaceDir,`build/r4-slide-${i+1}.layout.json`),await layout.text());
}
console.log('Terminal six-slide draft and final-file previews exported.');
