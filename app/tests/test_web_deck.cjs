const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const web=path.join(__dirname,'../src/bela/interfaces/web');
const dictionary=JSON.parse(fs.readFileSync(path.join(web,'hr.json'),'utf8'));
for(const artwork of [null,'hungarian','standard','invalid'])for(const names of [null,'standard','hungarian'])for(const lang of ['en','hr']){
 const ctx=vm.createContext({localStorage:{getItem:key=>key==='bela.cardStyle'?artwork:key==='bela.suitNames'?names:null},document:{documentElement:{dataset:{}}},t:s=>lang==='hr'?(dictionary[s]||s):s,SYMBOLS:{H:'H',S:'S',D:'D',C:'C'}});
 vm.runInContext(fs.readFileSync(path.join(web,'preferences.js'),'utf8'),ctx);vm.runInContext(fs.readFileSync(path.join(web,'deck.js'),'utf8'),ctx);
 assert.equal(ctx.document.documentElement.dataset.cardStyle,artwork==='standard'?'standard':'hungarian');
 const expected=names==='hungarian'?{H:'Hearts',S:'Leaves',D:'Bells',C:'Acorns'}:{H:'Hearts',S:'Spades',D:'Diamonds',C:'Clubs'};
 for(const suit of 'HSDC')assert.equal(vm.runInContext('deckSuitNames().'+suit,ctx),lang==='hr'?dictionary[expected[suit]]:expected[suit]);
 assert.equal(vm.runInContext('deckRank("Q")',ctx),artwork==='standard'?'Q':lang==='hr'?dictionary.Ober:'Ober');
}
const fields=new Map(['setup-dialog','event-dialog','review-notes','review-note-status','review-note','setup-name'].map(id=>[id,{id,value:'',checked:false,open:true,type:'text'}]));
fields.get('review-note').value='Unsaved thought';fields.get('setup-name').value='My unfinished deal';
const ctx=vm.createContext({$:id=>fields.get(id),t:s=>s,reviewData:{},reviewDirty:true,document:{documentElement:{dataset:{cardStyle:'hungarian'}},querySelectorAll:()=>[...fields.values()]},render:()=>{fields.get('setup-name').value='reset';},renderTrump:()=>{},renderReview:()=>{fields.get('review-note').value='reset';},renderSetupPicker:()=>{},refreshDialogLanguage:()=>{}});
vm.runInContext(fs.readFileSync(path.join(web,'deck.js'),'utf8'),ctx);vm.runInContext('refreshDeckPresentation()',ctx);
assert.equal(fields.get('review-note').value,'Unsaved thought');assert.equal(fields.get('setup-name').value,'My unfinished deal');assert.equal(fields.get('review-notes').open,true);assert.equal(fields.get('review-note-status').textContent,'Unsaved note');
console.log('Independent persisted suit naming, both languages, artwork/ranks and unfinished input checks passed.');
