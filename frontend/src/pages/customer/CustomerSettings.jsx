// Purpose: Render the customer settings screen and connect its user interactions to shared application state and services.
import { Link, useNavigate } from 'react-router-dom';
import { Bell, SlidersHorizontal, ShieldCheck, LockKeyhole, LogOut } from 'lucide-react';
import { useAuth } from '../../context/useAuth';
import { customerCard,customerButton } from '../../components/customer/CustomerData';

// Render the customer settings view interface and connect its controls to the state and callbacks defined here.
export function CustomerSettingsView({onLogout}) {
  const sections=[
    [Bell,'Notifications','Review notifications addressed to your account.','Email, SMS and push preference editing is not available.','/customer/notifications','Open notifications'],
    [SlidersHorizontal,'Application Preferences','Your current application presentation.','Save your preferred language in My Profile. Currency: LKR. Light appearance. Currency and theme editing are unavailable.','/customer/profile','View My Profile'],
    [ShieldCheck,'Privacy','Your account data is scoped by authenticated access.','Visibility, data-sharing and analytics preference controls are not available.','/customer/credit-accounts','View My Credit Accounts'],
    [LockKeyhole,'Security & Account','Manage your current sign-in.','Password changes, two-factor authentication and session management are not available here.',null,null],
  ];
  return <div className="space-y-5"><div><h2>Settings</h2><p className="mt-2 text-sm text-[#52698A]">Review your preferences, privacy and account information.</p></div>{sections.map(([Icon,title,note,unavailable,path,label])=><section key={title} className={customerCard}><div className="flex items-start gap-5"><span className="shrink-0 rounded-full bg-[#E7F9F6] p-4 text-[#008C87]"><Icon size={29} aria-hidden="true"/></span><div className="min-w-0 flex-1"><h3 className="text-xl font-bold">{title}</h3><p className="mt-1 text-sm text-[#52698A]">{note}</p><div className="mt-4 border-t border-[#E1EAF4] pt-4"><p className="text-sm text-[#52698A]">{unavailable}</p>{path?<Link className={customerButton+' mt-4'} to={path}>{label}</Link>:<button type="button" className={customerButton+' mt-4'} onClick={onLogout}><LogOut size={18}/>Sign Out</button>}</div></div></div></section>)}<div className="customer-unavailable">Help-center and in-app support services are not currently available.</div></div>;
}
// Render the customer settings interface and connect its controls to the state and callbacks defined here.
export default function CustomerSettings() {
  const {logout}=useAuth(),navigate=useNavigate();
  return <CustomerSettingsView onLogout={()=>{logout();navigate('/login',{replace:true});}}/>;
}
