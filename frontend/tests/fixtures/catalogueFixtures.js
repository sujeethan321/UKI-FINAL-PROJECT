const stamp='2026-11-06T10:00:00';
export const categoryFixture=(patch={})=>({category_id:11,business_id:1,name:'Groceries',description:null,is_active:true,created_at:stamp,updated_at:stamp,...patch});
export const productFixture=(patch={})=>({product_id:31,business_id:1,category_id:11,category_name:'Groceries',name:'Rice',description:null,unit_price:'125.25',currency:'LKR',availability_status:'available',publication_status:'draft',created_at:stamp,updated_at:stamp,...patch});
export const memoryIntent=()=>{const flags=new Set();return {read:b=>flags.has(b),mark:b=>flags.add(b),clear:b=>flags.delete(b)};};
export function catalogueFixture(){
  let products=[productFixture()],categories=[categoryFixture()];const calls=[];
  const failure=status=>{throw {response:{status}};};
  const ownerProduct=row=>({...row,category_name:categories.find(c=>c.category_id===row.category_id)?.name||null});
  const api={
    businesses:async()=>({user_id:7,businesses:[{business_id:1,business_name:'Shop One',approval_status:'approved'},{business_id:2,business_name:'Shop Two',approval_status:'approved'},{business_id:3,business_name:'Pending Shop',approval_status:'pending'}]}),
    summary:async b=>{const rows=products.filter(p=>p.business_id===b);return {business_id:b,total_products_count:rows.length,available_products_count:rows.filter(p=>p.availability_status==='available'&&p.publication_status!=='archived').length,categories_count:categories.filter(c=>c.business_id===b).length,unpublished_products_count:rows.filter(p=>p.publication_status==='draft').length};},
    listProducts:async(b,{page,filters})=>{calls.push(['listProducts',b,page,filters]);const rows=products.filter(p=>p.business_id===b&&(!filters.q||p.name.includes(filters.q))&&(!filters.category_id||p.category_id===Number(filters.category_id))&&(!filters.availability_status||p.availability_status===filters.availability_status)&&(!filters.publication_status||p.publication_status===filters.publication_status));return {page,page_size:10,total:rows.length,products:rows.slice((page-1)*10,page*10).map(ownerProduct)};},
    listCategories:async(b,{page})=>{const rows=categories.filter(c=>c.business_id===b);return {page,page_size:10,total:rows.length,categories:rows.slice((page-1)*10,page*10)};},
    getProduct:async(b,id)=>{calls.push(['getProduct',b,id]);const row=products.find(p=>p.business_id===b&&p.product_id===id);return row?ownerProduct(row):failure(404);},
    createProduct:async(b,payload)=>{calls.push(['createProduct',b,payload]);const row=productFixture({product_id:products.length+100,business_id:b,currency:'LKR',...payload});products.push(row);return ownerProduct(row);},
    updateProduct:async(b,id,payload)=>{calls.push(['updateProduct',b,id,payload]);const row=products.find(p=>p.business_id===b&&p.product_id===id);if(!row)return failure(404);if(row.publication_status==='archived')return failure(409);Object.assign(row,payload);return ownerProduct(row);},
    createCategory:async(b,payload)=>{calls.push(['createCategory',b,payload]);if(categories.some(c=>c.business_id===b&&c.name.toLowerCase()===payload.name.toLowerCase()))return failure(409);const row=categoryFixture({category_id:categories.length+100,business_id:b,...payload});categories.push(row);return row;},
    updateCategory:async(b,id,payload)=>{calls.push(['updateCategory',b,id,payload]);const row=categories.find(c=>c.business_id===b&&c.category_id===id);if(!row)return failure(404);Object.assign(row,payload);return row;},
  };
  return {api,calls,store:memoryIntent(),setProducts:rows=>{products=rows;},setCategories:rows=>{categories=rows;}};
}
