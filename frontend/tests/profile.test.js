import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createProfileReader,parseProfile} from '../src/utils/profile.js';
import {createAuthSession,TOKEN_KEY,PROFILE_SIGNAL_KEY} from '../src/utils/authSession.js';

const identity={user_id:4,platform_role:'customer',account_status:'active',full_name:'Before',preferred_language:'en'};
const profile=(patch={})=>({...identity,email:'synthetic@example.com',phone:'0771234567',revision:'p1-'+'a'.repeat(64),...patch});
const deferred=()=>{let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});return {promise,resolve,reject};};
function readerFixture(overrides={}){
 const calls=[];let saved=profile();
 const api={getProfile:async()=>saved,updateProfile:async(changes,revision)=>{calls.push({changes,revision});saved=profile({...changes,revision:'p1-'+'b'.repeat(64)});return saved;},...overrides};
 const reader=createProfileReader({identity,api,refreshIdentity:async()=>({...saved}),signalProfileChanged:()=>calls.push('signal')});return {reader,calls,api};
}
test('profile DTO is identity-bound and strips unexpected secrets',()=>{
 const data=parseProfile(profile({password_hash:'private'}),identity);assert.equal(data.password_hash,undefined);
 for(const patch of [{user_id:5},{platform_role:'admin'},{account_status:'suspended'},{revision:'invalid'}])assert.throws(()=>parseProfile(profile(patch),identity));
});
test('save submits only approved fields and revision; verified success signals other tabs',async()=>{
 const f=readerFixture();await f.reader.start();const result=await f.reader.save({full_name:'தமிழ் பெயர்',preferred_language:'ta'});
 assert.equal(result.full_name,'தமிழ் பெயர்');assert.deepEqual(f.calls[0],{changes:{full_name:'தமிழ் பெயர்',preferred_language:'ta'},revision:'p1-'+'a'.repeat(64)});assert.equal(f.calls[1],'signal');assert.equal(f.reader.getSnapshot().notice,'Updated Successfully');f.reader.dispose();
});
test('invalid and protected fields are rejected before requests',async()=>{
 const f=readerFixture();await f.reader.start();for(const changes of [{full_name:' ',preferred_language:'en'},{full_name:'Valid',preferred_language:'fr'},{full_name:'Valid',preferred_language:'en',phone:'123'}])await f.reader.save(changes);
 assert.equal(f.calls.length,0);f.reader.dispose();
});
test('stale conflict retains data, offers reload and does not retry automatically',async()=>{
 const f=readerFixture({updateProfile:async()=>{throw {response:{status:409,data:{detail:'private SQL'}}};}});await f.reader.start();await f.reader.save({full_name:'Draft',preferred_language:'en'});assert.match(f.reader.getSnapshot().error,/another tab/);assert.equal(f.reader.getSnapshot().data.full_name,'Before');assert.ok(!f.reader.getSnapshot().saving);f.reader.dispose();
});
test('logout cancels late save and never broadcasts previous user values',async()=>{
 const pending=deferred(),f=readerFixture({updateProfile:()=>pending.promise});await f.reader.start();const work=f.reader.save({full_name:'Late',preferred_language:'en'});f.reader.dispose();pending.resolve(profile({full_name:'Late'}));await work;assert.equal(f.reader.getSnapshot().data,null);assert.equal(f.calls.length,0);
});
test('strict-mode restart invalidates the old profile load',async()=>{
 const pending=deferred();let count=0;const f=readerFixture({getProfile:()=>++count===1?pending.promise:Promise.resolve(profile())});const old=f.reader.start();f.reader.dispose();await f.reader.start();pending.resolve(profile({full_name:'Stale'}));await old;assert.equal(f.reader.getSnapshot().data.full_name,'Before');f.reader.dispose();
});
function sessions(getCurrentUser){
 const values=new Map();const storage=()=>({getItem:key=>values.get(key),setItem:(key,value)=>values.set(key,value),removeItem:key=>values.delete(key)});
 const options={storage,loginUser:async()=>({access_token:'shared-profile-token'}),getCurrentUser};
 return {first:createAuthSession(options),second:createAuthSession(options),values};
}
test('in-place identity refresh keeps token, authenticated state and browser login policy',async()=>{
 let user={...identity};const f=sessions(async()=>user);await f.first.login('synthetic@example.com','fixture');await f.second.restore();
 const observed=[];f.first.subscribe(()=>observed.push(f.first.getSnapshot()));user={...user,full_name:'After',preferred_language:'si'};await f.first.refreshIdentity();
 assert.equal(f.first.getSnapshot().token,'shared-profile-token');assert.ok(observed.every(value=>value.token&&value.user&&!value.loading));
 f.first.signalProfileChanged();assert.equal(f.values.get(TOKEN_KEY),'shared-profile-token');const signal=f.values.get(PROFILE_SIGNAL_KEY);assert.match(signal,/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);assert.ok(!signal.includes('After'));assert.ok(!signal.includes('shared-profile-token'));
 await f.second.refreshIdentity();assert.equal(f.second.getSnapshot().user.full_name,'After');await assert.rejects(f.second.login('other@example.com','fixture'),error=>error.code==='BROWSER_ALREADY_SIGNED_IN');
});
test('late identity refresh cannot replace another login after logout',async()=>{
 const pending=deferred();let wait=false;const f=sessions(()=>wait?pending.promise:Promise.resolve(identity));await f.first.login('a@example.com','fixture');wait=true;const work=f.first.refreshIdentity();f.first.logout();pending.resolve({...identity,full_name:'Late'});await work;assert.equal(f.first.getSnapshot().user,null);
});
test('wrong role during identity refresh is rejected and signs out safely',async()=>{
 let changed=false;const f=sessions(async()=>({...identity,platform_role:changed?'admin':'customer'}));await f.first.login('a@example.com','fixture');changed=true;await assert.rejects(f.first.refreshIdentity());assert.equal(f.first.getSnapshot().token,null);
});
test('network refresh errors do not clear a valid token',async()=>{
 let failed=false;const f=sessions(async()=>{if(failed)throw Error('offline');return identity;});await f.first.login('a@example.com','fixture');failed=true;await assert.rejects(f.first.refreshIdentity());assert.equal(f.first.getSnapshot().token,'shared-profile-token');
});
test('profile provider listens to metadata-only signals without calling restore',async()=>{
 const source=await readFile(new URL('../src/context/AuthContext.jsx',import.meta.url),'utf8');assert.ok(source.includes('event?.key===PROFILE_SIGNAL_KEY'));assert.ok(source.includes('session.refreshIdentity()'));assert.ok(source.includes('key={state.token || "signed-out"}'));
 const api=await readFile(new URL('../src/services/profileService.js',import.meta.url),'utf8');assert.ok(api.includes("'If-Match':revision"));assert.ok(!api.includes('user_id'));
 for(const lang of ['en','ta','si']){const labels=JSON.parse(await readFile(new URL(`../src/i18n/locales/application.${lang}.json`,import.meta.url),'utf8'));for(const key of ['Personal Profile','Display Name','Preferred Language','Updated Successfully'])assert.ok(labels[key]);}
});
