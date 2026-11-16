import { Link, useNavigate, useOutletContext } from 'react-router-dom';
import { useState } from 'react';
import { Store, LockKeyhole, Monitor, ShieldCheck, LogOut } from 'lucide-react';
import { useAuth } from '../../context/useAuth';

const card='rounded-xl border border-[#E1EAF4] bg-white p-5';
const field='mt-2 block w-full rounded-lg border border-[#DAE5F3] bg-[#F8FBFE] px-3 py-2.5 text-sm';
export function ShopOwnerSettingsView({user, businesses=[], businessId, onBusiness, onLogout}) {
  const business=businesses.find(b=>b.business_id===businessId);
  return <div className="space-y-4"><div className="owner-page-heading"><h2>Settings</h2><p>Review your shop information and account settings.</p></div>
    <section className={card}><h3 className="text-xl font-bold">Shop Settings</h3><p className="mt-1 text-sm text-[#52698A]">Your linked business information.</p><label className="mt-4 block text-sm font-semibold">Business<select value={businessId||''} onChange={e=>onBusiness(Number(e.target.value))} className={field}><option value="">Select business</option>{businesses.map(b=><option key={b.business_id} value={b.business_id}>{b.business_name}</option>)}</select></label><div className="mt-4 grid gap-4 md:grid-cols-2"><label className="text-sm">Shop Name<input className={field} readOnly value={business?.business_name||''}/></label><label className="text-sm">Business Category<input className={field} readOnly value={business?.business_type||''}/></label></div><p className="mt-4 flex items-center gap-2 text-sm text-[#52698A]"><Store size={18} aria-hidden="true"/>Shop details and logo editing are not available here.</p></section>
    <section className={card}><h3 className="text-xl font-bold">Credit &amp; Delivery Preferences</h3><div className="mt-4 grid gap-5 md:grid-cols-2"><div><h4 className="font-semibold">Credit Preferences</h4><p className="mt-2 text-sm text-[#52698A]">Credit limits and payment terms are managed for each customer.</p><Link to="/shop-owner/customers" className="mt-3 inline-block text-sm font-semibold text-[#008C87] underline">Manage customer credit accounts</Link></div><div className="md:border-l md:border-[#E1EAF4] md:pl-5"><h4 className="font-semibold">Delivery Preferences</h4><p className="mt-2 text-sm text-[#52698A]">Shop-wide delivery defaults and radius settings are not available.</p><Link to="/shop-owner/deliveries" className="mt-3 inline-block text-sm font-semibold text-[#008C87] underline">Manage delivery requests</Link></div></div></section>
    <section className={card}><h3 className="text-xl font-bold">Notifications &amp; Language</h3><div className="mt-4 grid gap-5 md:grid-cols-2"><div><h4 className="font-semibold">Notification Preferences</h4><p className="mt-2 text-sm text-[#52698A]">Alert preference editing is not available.</p><Link to="/shop-owner/notifications" className="mt-3 inline-block text-sm font-semibold text-[#008C87] underline">Open notification inbox</Link></div><label className="text-sm">Recorded preferred language<input readOnly className={field} value={user?.preferred_language||'Not recorded'}/><span className="mt-2 block text-xs text-[#64748B]">Language editing and application translation are not available here.</span></label></div></section>
    <section className={card}><h3 className="text-xl font-bold">Account &amp; Security</h3><div className="mt-3 divide-y divide-[#E1EAF4]">{[[LockKeyhole,'Password','Password changes are not available here.'],[Monitor,'Active Sessions','Session management is not available here.'],[ShieldCheck,'Account Status',user?.account_status||'Unavailable']].map(([Icon,title,note])=><div key={title} className="flex flex-wrap items-center gap-3 py-4"><Icon size={21} aria-hidden="true"/><h4 className="w-36 text-sm font-semibold">{title}</h4><p className="text-sm text-[#52698A]">{note}</p></div>)}<button type="button" onClick={onLogout} className="flex items-center gap-3 py-4 text-sm font-semibold text-[#008C87]"><LogOut size={19}/>Sign Out</button></div></section>
  </div>;
}
export default function ShopOwnerSettings() {
  const {user,logout}=useAuth(),navigate=useNavigate();
  const {businesses=[]}=useOutletContext() || {};
  const [selected,setSelected]=useState(null);
  const business=businesses.find(b=>b.business_id===selected)||businesses[0];
  return <ShopOwnerSettingsView user={user} businesses={businesses} businessId={business?.business_id} onBusiness={setSelected} onLogout={()=>{logout();navigate('/login',{replace:true});}}/>;
}
