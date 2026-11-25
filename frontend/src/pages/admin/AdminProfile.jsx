// Purpose: Render the admin profile screen and connect its user interactions to shared application state and services.
import ProfileForm from '../../components/profile/ProfileForm';
import {useAuth} from '../../context/useAuth';
// Render the admin profile interface and connect its controls to the state and callbacks defined here.
export default function AdminProfile(){
 const {user,isAuthenticated}=useAuth();
 return isAuthenticated&&user?.platform_role==='admin'&&user?.account_status==='active'?<ProfileForm/>:null;
}
