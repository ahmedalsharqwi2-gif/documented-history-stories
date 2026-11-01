/** Supported source-fit worlds. These are scene semantics, not palette presets. */
export const HISTORY_WORLDS={
 aqueduct_valley:{focus:'aqueduct',source_ids:['311','344'],settings:['valley_route','stone_workbench','pier_foundation','arch_assembly','channel_cutaway','water_route','inspection_walkway','valley_overview'],objects:['terrain_and_aqueduct','stone_block','pier','voussoirs_and_keystone','water_channel','flow_markers','channel_and_joint','whole_crossing'],actions:['reveal_crossing','inspect_surface','trace_load','place_keystone','reveal_water_section','follow_water','inspect_joint','reveal_system'],shots:['wide_establishing','macro_detail','low_angle','lateral_close','section_push','tracking','inspection_close','pullback']},
 arena_complex:{focus:'arena',source_ids:['164','38'],settings:['city_exterior','seating_bowl','radial_passage','tier_cutaway','arch_detail','circulation_diagram','conservation_workbench','arena_overview'],objects:['elliptical_enclosure','seating_steps','radial_corridor','source_tiers','arch_and_load','route_markers','stone_joint','whole_complex'],actions:['enter_complex','reveal_seating','follow_passage','reveal_tiers','trace_load','follow_routes','inspect_surface','pull_out'],shots:['wide_establishing','interior_orbit','corridor_tracking','section_push','macro_detail','overhead','inspection_close','pullback']},
 canal_trough:{focus:'cast_iron_trough',source_ids:['1303'],settings:['canal_bank','iron_workbench','pier_section','trough_assembly','water_cutaway','towpath_route','joint_inspection','canal_overview'],objects:['trough_section_and_bank','iron_plate','stone_pier_section','iron_trough','water_and_iron_section','towpath_and_water','trough_joint','illustrative_canal_section'],actions:['reveal_section','inspect_surface','trace_support','join_trough_section','reveal_water_section','follow_water','inspect_joint','reveal_system'],shots:['wide_establishing','macro_detail','low_angle','lateral_close','section_push','tracking','inspection_close','pullback']}
};
for(const [id,spec] of Object.entries(HISTORY_WORLDS)){
 spec.focal_objects=[...spec.objects];
 spec.minimum_distinct_settings=4;
 spec.compatible_beats=spec.settings.map((setting,i)=>({setting,focal_object:spec.objects[i],action:spec.actions[i]}));
 spec.subject_contract={required_source_url_contains:id==='canal_trough'?'/en/list/1303/':'https://whc.unesco.org/en/list/',supported_topic_keys:{aqueduct_valley:['segovia-aqueduct-unesco','pont-du-gard-aqueduct','unesco-311-aqueduct','unesco-344-aqueduct'],arena_complex:['arles-amphitheatre-unesco','unesco-164-arena','unesco-38-arena'],canal_trough:['unesco-1303-cast_iron_trough']}[id]};
}
export function historyPlan(story){
 const plan=story.visual_plan,world=HISTORY_WORLDS[plan?.world];
 if(!world||plan.version!==1)throw Error('History v2 requires an explicit supported topic world');
 const source=new URL(story.source?.url||'https://invalid.invalid');
 const site=source.pathname.match(/^\/en\/list\/(\d+)\/?$/)?.[1];
 if(source.hostname!=='whc.unesco.org'||!world.source_ids.includes(site))throw Error('History world does not fit the supplied UNESCO source');
 const focus=story.visual_contract?.focus;
 if(focus!==world.focus)throw Error('History source geometry contract conflicts with topic world');
 if(plan.world!=='canal_trough'){
  const expected={'311':2,'344':3,'164':2,'38':3}[site];
  if(story.visual_contract.tier_count!==expected)throw Error('History source tier count must remain exact');
 }
 if(!Array.isArray(plan.scenes)||plan.scenes.length!==8||story.scenes?.length!==8)throw Error('History world requires eight authored director beats');
 plan.scenes.forEach((row,i)=>{
  const asset=world.settings.indexOf(row.setting);
  if(row.id!==story.scenes[i].id||asset<0||row.focal_object!==world.objects[asset]||row.action!==world.actions[asset]||!world.shots.includes(row.shot)||typeof row.state_change!=='string'||!row.state_change.trim())throw Error('History director beat has unsupported semantics or identity');
 });
 if(new Set(plan.scenes.map(row=>row.setting)).size<4)throw Error('History film needs distinct physical settings');
 return {world:plan.world,focus,source_id:site,scenes:plan.scenes};
}
export function makeHistoryPlan(story,world){
 const spec=HISTORY_WORLDS[world];if(!spec)throw Error('Unsupported history topic world');
 return {version:1,world,scenes:story.scenes.map((scene,i)=>({id:scene.id,setting:spec.settings[i],focal_object:spec.objects[i],action:spec.actions[i],shot:spec.shots[i],state_change:'Reveal the source-supported '+spec.objects[i]+' through '+spec.actions[i]}))};
}
