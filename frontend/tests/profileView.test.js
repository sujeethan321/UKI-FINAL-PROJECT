import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createElement as h} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {MemoryRouter} from 'react-router-dom';
import {createServer} from 'vite';
import {readFile} from 'node:fs/promises';

test('personal profile form preserves role designs and read-only security boundary',async t=>{
 const server=await createServer({logLevel:'silent',appType:'custom',server:{middlewareMode:true,hmr:false}});
 try{
  const {ProfileFormView:View,default:Form}=await server.ssrLoadModule('/src/components/profile/ProfileForm.jsx');
  const {AuthContext}=await server.ssrLoadModule('/src/context/AuthContext.jsx');
  const data={user_id:4,platform_role:'customer',account_status:'active',full_name:'Synthetic display',email:'synthetic@example.com',phone:'0771234567',preferred_language:'en',revision:'p1-'+'a'.repeat(64)};
  const ready={data,loading:false,saving:false,error:'',notice:''};const actions={load(){},save(){}};const render=state=>renderToStaticMarkup(h(View,{state,actions}));
  await t.test('editable name and language, read-only actual email/phone, no privileged inputs',()=>{
   const html=render(ready);for(const value of ['Personal Profile','Display Name','Preferred Language','0771234567','synthetic@example.com','தமிழ்','සිංහල','Save Changes'])assert.ok(html.includes(value),value);
   assert.equal((html.match(/readOnly=""/g)||[]).length,2);assert.ok(!html.includes('type="password"'));assert.ok(!html.includes('approval_status'));assert.ok(!html.includes('type="file"'));
  });
  await t.test('loading, success and conflict feedback are explicit',()=>{
   assert.ok(render({...ready,data:null,loading:true}).includes('role="status"'));assert.ok(render({...ready,notice:'Updated Successfully'}).includes('Updated Successfully'));assert.ok(render({...ready,error:'Profile changed in another tab. Reload before saving again.'}).includes('role="alert"'));
  });
  await t.test('all four authenticated roles mount same ordinary form',()=>{
   for(const role of ['admin','customer','shop_owner','driver']){
    const auth={isAuthenticated:true,user:{...data,platform_role:role},token:'fixture',refreshIdentity(){},signalProfileChanged(){}};
    assert.ok(renderToStaticMarkup(h(AuthContext.Provider,{value:auth},h(Form))).includes('Personal Profile'));
   }
   assert.equal(renderToStaticMarkup(h(AuthContext.Provider,{value:{isAuthenticated:false}},h(Form))),'');
  });
  await t.test('Admin menu adds profile without sidebar changes; Driver personal form is independent of optional documents',async()=>{
   const {default:Layout}=await server.ssrLoadModule('/src/layouts/AdminLayout.jsx');const auth={isAuthenticated:true,user:{...data,platform_role:'admin'},logout(){}};
   const html=renderToStaticMarkup(h(MemoryRouter,null,h(AuthContext.Provider,{value:auth},h(Layout))));assert.ok(html.includes('Account actions'));
   const layoutSource=await readFile(new URL('../src/layouts/AdminLayout.jsx',import.meta.url),'utf8');assert.ok(layoutSource.includes('links={[{to:"/admin/profile",label:"Personal Profile"}]}'));
   const {default:Driver}=await server.ssrLoadModule('/src/pages/driver/DriverProfile.jsx');const driver=renderToStaticMarkup(h(MemoryRouter,null,h(AuthContext.Provider,{value:{...auth,token:'fixture',user:{...data,platform_role:'driver'}}},h(Driver))));assert.ok(driver.includes('Personal Profile'));
  });
 }finally{await server.close();}
});
