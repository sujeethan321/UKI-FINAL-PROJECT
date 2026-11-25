// Purpose: Wrap admin support API calls so components use a shared request interface instead of building HTTP requests themselves.
import {supportApi} from './supportService';
export default supportApi('/admin/support/cases');
