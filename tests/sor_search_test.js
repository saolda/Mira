// Execute the exact production search asset with a minimal DOM double.
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
let focused=null,nextTimer=0;const timers=new Map();
class Element{
 constructor(text=''){this.textContent=text;this.children=[];this.events={};this.value='';this.scrolls=[];const classes=new Set();this.classList={add:c=>classes.add(c),remove:c=>classes.delete(c),contains:c=>classes.has(c)};}
 append(...items){this.children.push(...items);}replaceChildren(){this.children=[];}
 addEventListener(name,fn){this.events[name]=fn;}scrollIntoView(value){this.scrolls.push(value);}focus(){focused=this;}
}
const input=new Element(),list=new Element(),count=new Element(),body=new Element();
const targets=[new Element('Café observation'),new Element('Straße scientific finding'),new Element('Additional scientific finding'),new Element('<img onerror=alert(1)>')];
const ids={'paper-search':input,'paper-results':list,'paper-match-count':count};
const document={body,getElementById:id=>ids[id],createElement:()=>new Element(),querySelectorAll:q=>q==='.paper-highlight'?targets.filter(t=>t.classList.contains('paper-highlight')):targets};
const window={};window.self=window;window.top=window;
vm.runInNewContext(fs.readFileSync(process.argv[2],'utf8'),{window,document,setTimeout:(fn,delay)=>{assert.equal(delay,2400);timers.set(++nextTimer,fn);return nextTimer;},clearTimeout:id=>timers.delete(id)});
const search=q=>{input.value=q;input.events.input();return list.children.map(li=>li.children[0].textContent);};
const key=k=>{const e={key:k,preventDefault(){this.prevented=true;}};input.events.keydown(e);return e;};
assert.deepEqual(search(' CAFE\u0301  '),['Café observation']);
assert.deepEqual(search('ＳＴＲＡＳＳＥ'),['Straße scientific finding']);
assert.deepEqual(search(' SCIENTIFIC   finding '),['Straße scientific finding','Additional scientific finding']);
input.focus();assert(key('ArrowDown').prevented);assert(targets[1].classList.contains('paper-highlight'));assert.equal(focused,input);
key('ArrowDown');assert(targets[2].classList.contains('paper-highlight'));assert(!targets[1].classList.contains('paper-highlight'));assert.equal(focused,input);
key('ArrowUp');assert(targets[1].classList.contains('paper-highlight'));key('Enter');assert.equal(focused,input);
list.children[1].children[0].onclick();assert.equal(focused,targets[2]);assert.equal(targets[2].scrolls.at(-1).block,'center');
assert.equal(timers.size,1);[...timers.values()][0]();assert(!targets[2].classList.contains('paper-highlight'));
assert.deepEqual(search('<img'),['<img onerror=alert(1)>']);assert.equal(list.children[0].children[0].textContent,'<img onerror=alert(1)>');
assert.deepEqual(search('does not exist'),[]);assert.equal(count.textContent,'No matching passages');assert(!key('Enter').prevented);
assert.deepEqual(search(''),[]);assert.equal(count.textContent,'');console.log('SOR incremental Unicode search, safe results, keyboard navigation, focus and highlighting passed.');
