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
 text(s,'draft-footer',`DRAFT / 04 Oct 2026 23:03 UTC / ${String(number).padStart(2,'0')}`,64,675,1152,24,17,dark?'#BDCECA':C.muted);
 return s;
}
function notes(s,title,body,sources){
 const value=`AI-assisted factual draft for participant review. Evidence scope: 2026-10-04 23:03 UTC. Stage 1 candidate 4026ec7 is rejected; final run outcome remains pending.\n\n${title}\n${body}\n\nSources\n${sources.join('\n')}\n\nPrivate source links may require repository access. This presentation is not room-video evidence.`;
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
 text(s,'subject','Tablekeeper factory',64,154,1150,64,48,'#B8DAD0',false);
 text(s,'objective','Seven BAND seats are configured to build and review\nfour incremental application stages.',64,267,1090,94,32,C.white);
 text(s,'seven','7',64,397,100,119,100,'#B8DAD0',true);
 text(s,'registered','registered roles',178,439,420,46,29,C.white);
 text(s,'one','1',714,397,100,119,100,'#B8DAD0',true);
 text(s,'active','active model seat at a time',826,425,388,90,29,C.white);
 text(s,'roles','PM / Architect / Designer / Backend / Frontend / QA / Reviewer',64,551,1152,39,25,C.white);
 text(s,'runtime','All seven use Codex 0.160.0 with gpt-6-astra. BAND SDK 4.0.0.',64,602,1152,38,23,'#BDCECA');
 notes(s,'Factory objective and ownership','One active model turn limits shared-checkout write conflicts. Seven registrations do not prove seven seats have completed meaningful work in this attempt. All efforts remain medium except Architect, QA and Reviewer, which use high. The single all-stage task dispatch occurred at 2026-10-04T21:06:55.943682Z in room 12cde259-0fcd-4551-84c7-52c443cb5600. This deck makes no final stage or dollar-spend claim.',[`${O}/packaging/FACTORY.draft.md`,`${F}/evidence/run5-launch-20261004/dispatch-verification.json`,`${GH}run5-launch-20261004`]);
}
{
 const s=slide('Complete handoffs and an independent gate',2);
 const steps=[['1  Assignment','PM sends full requirements,\nrevision, owner and limits.'],['2  Receipt','The peer checks every part\nand acknowledges its digest.'],['3  Candidate','The owner returns a commit\nwith commands and results.'],['4  Release gate','An independent Reviewer\naccepts or returns defects.']];
 steps.forEach(([head,body],i)=>{text(s,`step-${i}`,head,64,176+i*112,314,35,26,C.teal,true);text(s,`step-body-${i}`,body,64,215+i*112,314,67,23);});
 s.images.add({blob:new Uint8Array(await fs.readFile(path.join(workspaceDir,'assets/architecture-handoff.jpg'))),contentType:'image/jpeg',fit:'contain',position:{left:400,top:190,width:816,height:382},alt:'Actual Run 5 BAND room showing PM assignment and Architect full-part acknowledgment. Still captured 21:30–21:32 UTC.'});
 text(s,'still-caption','Actual Run 5 room still, 21:30–21:32 UTC.\nThe Architect confirms all 4 parts and the payload digest.',400,596,816,63,21,C.muted);
 notes(s,'Handoff and gate mechanism','The still is the original real room image, preserved without cropping or content edits. It shows PM planning acceptance and the Architect ACK/IN_PROGRESS statement. Product behavior remains NOT_TESTED in that earlier screenshot. It is a still image, not a video or evidence of stage acceptance. Reviewer authority and finite repair limits come from the standing mandates and launch packet. The transport digest acknowledgment proves delivery only.',[`${O}/packaging/media/architecture-handoff.jpg`,`${O}/packaging/media/architecture-handoff.provenance.json`,`${F}/mandates/factory-pm.md`,`${F}/mandates/factory-reviewer.md`,`${F}/protocols`]);
}
{
 const s=slide('Two defects closed in host checks',3);
 text(s,'subtitle','Independent QA recheck on candidate 4026ec7',64,146,1152,37,27,C.teal);
 table(s,'qa-timeline',[
 ['UTC','Candidate','Recorded event'],
 ['22:31','68afbf8','PM receives two independently reproduced valid-input defects.'],
 ['22:41','4026ec7','Backend returns repair 7e82648. PM acknowledges its full handoff.'],
 ['22:48 / 22:50','4026ec7','QA closes both defects. PM acknowledges the matching digest.']
 ],206,[175,195,782],[54,88,88,88],24);
 text(s,'focused','5 focused groups',64,566,360,40,29,C.teal,true);
 text(s,'baseline','11 baseline groups',438,566,370,40,29,C.teal,true);
 text(s,'extras','7 additional groups',837,566,379,40,29,C.teal,true);
 text(s,'limit','All passed on host Python 3.13.5. These overlapping groups do not establish stage acceptance.',64,624,1152,39,22,C.muted);
 notes(s,'Actual QA, fix and defect closure chronology','Rejected candidate: 68afbf86127ae9b2b5dc8ecc56a0e9c78e6a69f1, implementation 249e5712624d20ca02c9680eb6ec60ff3865bcb8. QA found valid 9999-12-31 availability returned 422 and a valid 5,000-digit positive decimal query returned 400. PM accepted both defects for repair 2 of 3 at 2026-10-04T22:31:48.528483Z. Backend implementation 7e82648b4f4feb1c74015f9c551626ba3a36851c and record-only candidate 4026ec71ac6cf5ae0ebe6e998d77fd4a475a8c4d share stage tree 6000d94a5acbcab53438120b6d7f2624b4eceba4. Owner return ACK: 22:41:21.572593Z. QA recheck execution: 22:45:49.499952–22:45:55.494112Z. QA final event eb1a0344-5318-49df-b642-dd4367139c9b at 22:48:51.604927Z. PM ACK da610b06-becf-4e27-b68e-48fbd0853caf at 22:50:04.354683Z confirms digest 55b42848be78b9a165d280f08247e69af53a1c8ef2175f47b6089b59aa306b9e. Defect closure is specific to that candidate and host layer.',[`${F}/evidence/run5-stage1-independent-qa-20261004/README.md`,`${F}/evidence/run5-stage1-repair2-20261004/manifest.json`,`${F}/evidence/run5-stage1-qa-recheck-20261004/report.md`,`${F}/evidence/run5-stage1-qa-recheck-20261004/execution.json`,`${F}/evidence/run5-stage1-qa-recheck-20261004/public-events.json`,`${GH}run5-stage1-qa-recheck-20261004`]);
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
 text(s,'resource-warning','The 2 GiB global cap also covers VM and daemon overhead.',64,578,1152,40,28,C.amber,true);
 text(s,'autonomy-limit','Application state continuity and full 2 GiB application capacity remain unverified.',64,624,1152,38,23,C.muted);
 notes(s,'OOM, operator intervention and current user cap','At 22:07:51.903833782Z the architecture review container was OOM-killed under a 1,024 MiB global OrbStack ceiling despite a 2 GiB per-container limit. Docker responsiveness recovered before the first operator restart. The operator set 4,096 MiB at 22:30 and activated it with one stop/start at 22:31:18–22:31:24. Only the two verified existing Run 5 owner containers restarted. At the user’s later request, the operator set 2,048 MiB and performed a second stop/start at 22:49:06–22:49:11, restoring the same IDs. Docker reported 2,073,866,240 bytes of VM memory after the second intervention. Both changes interrupted the containers. Application/session-state continuity was not tested. No BAND instructions, product edits, model/seat restarts or operator product-test reruns accompanied these interventions. Do not claim fully autonomous or uninterrupted execution, full specified application capacity, or organizer acceptance of this intervention. A later independent gate must address the actual environment.',[`${F}/evidence/run5-orbstack-memory-repair-20261004/README.md`,`${F}/evidence/run5-orbstack-memory-repair-20261004/orbstack-memory-activation.json`,`${F}/evidence/run5-user-2g-cap-20261004/orbstack-user-2g-cap.json`,`${GH}run5-orbstack-memory-repair-20261004`,`${GH}run5-user-2g-cap-20261004`]);
}
{
 const s=slide('Stage 1 rejected on three defect families',5);
 text(s,'snapshot','Independent Reviewer / 4026ec7 / 23:01 UTC',64,147,1152,40,28,C.amber);
 table(s,'reviewer-findings',[
 ['Confirmed finding','Expected behavior','Observed behavior'],
 ['Reset numeric fields use wrong JSON types','400','422'],
 ['Import contains corrupted completed receipts','Reject invalid state','204, then invalid replay'],
 ['Fixture capacity has 5,000 decimal digits','Accept valid capacity','400']
 ],219,[632,250,270],[54,88,99,99],24);
 text(s,'assertions','31/61 focused HTTP assertions passed; 30 failed.',64,589,1152,39,26,C.amber,true);
 text(s,'later-stages','Two host mechanism groups passed. Stages 2–4 remain incomplete.',64,632,1152,32,23,C.muted);
 notes(s,'Formal Reviewer rejection and unfinished stages','Independent gate decision GATE-S1 rejects exact candidate 4026ec71ac6cf5ae0ebe6e998d77fd4a475a8c4d. Final native public event 7f7848d9-1ce3-4f34-8f94-4f43643abf0c was recorded at 23:01:56 UTC (operator observation supplied by the coordinator); the unchanged Reviewer decision.md is preserved with this deck. Focused HTTP run at 22:56:50.326925–22:56:51.492479 UTC returned exit 1: 31 PASS / 30 FAIL assertions spanning three product defect families, not 30 independent defects. Ordinary fixture numeric fields with wrong JSON types returned 422 instead of required 400. Corrupted completed receipt responses imported with 204 and later replayed incomplete or inconsistent identities. A valid 5,000-digit fixture capacity returned 400 despite no specified maximum. Earlier date-max and long-query checks passed again. Two controlled host mechanism groups passed at 22:57:56.898707–22:57:57.182907 UTC; these do not establish HTTP or isolated concurrency conformance. Current clean container build, official isolated suite, Python 3.12 and exact resource gates remain separately BLOCKED/NOT_TESTED. As of the 23:03 UTC cutoff, PM was handling the bounded next repair; no new repaired candidate or acceptance is claimed. Stage 1 remains unaccepted and Stages 2–4 incomplete.',[`${O}/packaging/presentation/assets/reviewer-decision-2301.md`,`${O}/observation/presentation-state-20261004T2301Z.json`,`${F}/evidence/run5-stage1-qa-recheck-20261004/coverage.json`,`${F}/evidence/run5-stage1-qa-recheck-20261004/completion.json`]);
}
{
 const s=slide('Evidence still needed for the final package',6);
 text(s,'verification','Final verification',64,176,545,42,31,C.teal,true);
 text(s,'verification-list','Independent gate for a repaired candidate\nFresh-clone package and isolated checks\nClean startup and real Stage 2–4 UI verification\nFinal measured time and usage',64,238,596,235,26);
 text(s,'submission','Submission artifacts',680,176,536,42,31,C.teal,true);
 text(s,'submission-list','Genuine final full-session room export\nParticipant-reviewed README and FACTORY\nPublic judge access after authorization\nSubmission receipt after authorization',680,238,536,235,26);
 text(s,'video','The participant deferred video. Real room footage remains required.',64,528,1152,72,29,C.amber,true);
 text(s,'draft-disclosure','AI-assisted draft for participant review. Final outcomes and costs remain pending.',64,625,1152,39,23,C.muted);
 notes(s,'Final package and unresolved evidence','The participant deferred video. No video was created, and this slide deck does not substitute for the guide’s required real factory footage. README and FACTORY remain AI-assisted factual drafts. Participant authorship/review requirements remain visible and are not satisfied merely by calling an AI draft human-written. After the final coordinator report, preserve exact accepted/rejected commits, genuine full-session download and final consumption ledger. Follow the existing post-run plan from a new clone at a full final commit. Public release/default-branch selection and actual submission follow their applicable separate authority. Private tools remain separate from the canonical application repository, whose attempt branch is run-5. Navigation main is not the selected submission. No monetary spend or final usage total is inferred from token snapshots.',[`${O}/packaging/post-run-verification-plan.md`,`${F}/submission-templates/final-checklist.md`,`${F}/docs/attempt-branches.md`,`${O}/packaging/README.draft.md`,`${O}/packaging/FACTORY.draft.md`,'https://github.com/band-ai/dark-factory-wearedevs/blob/803560d2a678ace1414465c098eb0ab5380ffade/docs/participant-guide.md']);
}
await fs.writeFile(path.join(workspaceDir,'deck-source.json'),JSON.stringify({title:'MillieMoon Tablekeeper Factory Run 5',status:'DRAFT',snapshot_utc:'2026-10-04T23:03:00Z',snapshot_precision:'minute; final gate event reported 23:01:56 UTC',authoring:'AI-assisted factual draft for participant review',font,slides:transcript},null,2)+'\n');
await fs.writeFile(path.join(workspaceDir,'build/presentation.json'),JSON.stringify(presentation.toProto()));
const candidatePath=path.join(workspaceDir,'build/candidate-2303-r3.pptx');
await (await PresentationFile.exportPptx(presentation)).save(candidatePath);
const result=await finalizePresentation({explicitTotalSlideCount:6,requiredNativeTableOwnerSlides:[3,4,5],requiredNativeChartOwnerSlides:[],workspaceDir,candidatePath,finalPath:path.join(workspaceDir,'output/MillieMoon-Tablekeeper-Run5-DRAFT-2303-r3.pptx'),pythonExecutable:RUNTIME_PYTHON,integrityValidatorPath:path.join(SKILL_DIR,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(SKILL_DIR,'container_tools/inspect_presentation_layout_geometry.py'),layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-heading-fit','--require-native-table-slide','3','--require-native-table-slide','4','--require-native-table-slide','5'],fontPolicy:{basis:'design',families:[font]},verifyArtifactToolImport:true,receiptPath:path.join(workspaceDir,'build/validation-2303-r3.json')});
console.log(JSON.stringify(result));
const final=await PresentationFile.importPptx(await FileBlob.load(path.join(workspaceDir,'output/MillieMoon-Tablekeeper-Run5-DRAFT-2303-r3.pptx')));
for(let i=0;i<final.slides.items.length;i++){
 const s=final.slides.items[i];
 const png=await final.export({slide:s,format:'png',scale:1});
 await fs.writeFile(path.join(workspaceDir,`previews/slide-${i+1}.png`),new Uint8Array(await png.arrayBuffer()));
 const layout=await s.export({format:'layout'});await fs.writeFile(path.join(workspaceDir,`build/slide-${i+1}.layout.json`),await layout.text());
}
console.log('Six-slide editable draft and final-file previews exported.');
