import ProfileForm from '../../components/profile/ProfileForm';
import {useAuth} from '../../context/useAuth';
export default function AdminProfile(){
 const {user,isAuthenticated}=useAuth();
 return isAuthenticated&&user?.platform_role==='admin'&&user?.account_status==='active'?<ProfileForm/>:null;
}
