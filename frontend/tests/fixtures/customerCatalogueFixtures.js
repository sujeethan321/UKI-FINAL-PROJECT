export const publicShop=(patch={})=>({business_id:1,business_name:'Local Shop',product_count:1,...patch});
export const publicCategory=(patch={})=>({category_id:11,business_id:1,name:'Groceries',description:'Everyday products',...patch});
export const publicProduct=(patch={})=>({product_id:31,business_id:1,category_id:11,category_name:'Groceries',name:'Rice',description:'Retail unit',unit_price:'125.25',currency:'LKR',availability_status:'available',...patch});
export function customerCatalogueFixture(){
  let shops=[publicShop(),publicShop({business_id:2,business_name:'Other Shop',product_count:1})],products=[publicProduct(),publicProduct({product_id:32,business_id:2,name:'Other rice',category_id:null,category_name:null})],categories=[publicCategory()];const calls=[];
  const fail=()=>{throw {response:{status:404}};};
  const page=(rows,key,current)=>({page:current,page_size:10,total:rows.length,[key]:rows.slice((current-1)*10,current*10)});
  const api={shops:async({page:current,q})=>{calls.push(['shops',current,q]);return page(shops.filter(s=>s.product_count>0&&s.business_name.toLowerCase().includes(q.toLowerCase())),'shops',current);},
    shop:async id=>{calls.push(['shop',id]);return shops.find(s=>s.business_id===id)||fail();},
    categories:async(id,{page:current})=>{calls.push(['categories',id,current]);return page(categories.filter(c=>c.business_id===id),'categories',current);},
    products:async(id,{page:current,filters})=>{calls.push(['products',id,current,filters]);return page(products.filter(p=>p.business_id===id&&(!filters.q||p.name.toLowerCase().includes(filters.q.toLowerCase()))&&(!filters.category_id||p.category_id===Number(filters.category_id))&&(!filters.availability_status||p.availability_status===filters.availability_status)),'products',current);},
    product:async(id,productId)=>{calls.push(['product',id,productId]);return products.find(p=>p.business_id===id&&p.product_id===productId)||fail();},
  };
  return {api,calls,setShops:rows=>{shops=rows;},setProducts:rows=>{products=rows;},setCategories:rows=>{categories=rows;}};
}
