import {useAuth} from '../../context/useAuth';
import {useDriverProfile} from '../../hooks/useDriverProfile';

function Resource({user,children}) {
  const state=useDriverProfile(user.user_id);
  if(state.loading)return <p role="status" className="driver-unavailable">Loading your Driver profile...</p>;
  if(state.error)return <div role="alert" className="driver-unavailable"><p>{state.error}</p><button type="button" onClick={state.reload} className="mt-3 rounded-lg border border-[#DAE5F3] px-4 py-2 text-sm">Retry profile</button></div>;
  return children(state.data,user,state.reload);
}
export default function DriverAccountResource({children}) {
  const {user,token,isAuthenticated}=useAuth();
  return isAuthenticated&&user?.platform_role==='driver'&&user.account_status==='active'?<Resource key={user.user_id+':'+token} user={user}>{children}</Resource>:null;
}
