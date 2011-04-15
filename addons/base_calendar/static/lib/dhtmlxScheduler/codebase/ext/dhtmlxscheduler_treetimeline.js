scheduler.attachEvent("onTimelineCreated",function(A){if(A.render=="tree"){A.y_unit_original=A.y_unit;A.y_unit=scheduler._getArrayToDisplay(A.y_unit_original);scheduler.form_blocks[A.name]={render:function(C){var B="<div class='dhx_section_timeline' style='overflow: hidden; height: "+C.height+"px'></div>";return B},set_value:function(D,I,G,C){var J=scheduler._getArrayForSelect(scheduler.matrix[C.type].y_unit_original,C.type);D.innerHTML="";var F=document.createElement("select");D.appendChild(F);var H=D.getElementsByTagName("select")[0];for(var E=0;E<J.length;E++){var B=document.createElement("option");B.value=J[E].key;if(B.value==G[scheduler.matrix[C.type].y_property]){B.selected=true}B.innerHTML=J[E].label;H.appendChild(B)}},get_value:function(D,C,B){return D.firstChild.value},focus:function(B){}}}});scheduler.attachEvent("onBeforeViewRender",function(J,E,H){var F={};if(J=="tree"){var I;var D,A,B;var C;var G;if(E.children){I=H.folder_dy||H.dy;if(H.folder_dy&&!H.section_autoheight){A="height:"+H.folder_dy+"px;"}D="dhx_row_folder";B="dhx_matrix_scell folder";C="<div class='dhx_scell_expand'>"+((E.open)?"-":"+")+"</div>";G=(H.folder_events_available)?"dhx_data_table folder_events":"dhx_data_table folder"}else{I=H.dy;D="dhx_row_item";B="dhx_matrix_scell item";C="";G="dhx_data_table"}td_content="<div class='dhx_scell_level"+E.level+"'>"+C+"<div class='dhx_scell_name'>"+(scheduler.templates[H.name+"_scale_label"](E.key,E.label,H)||E.label)+"</div></div>";F={height:I,style_height:A,tr_className:D,td_className:B,td_content:td_content,table_className:G}}return F});var section_id_before;scheduler.attachEvent("onBeforeEventChanged",function(D,A,C){if(scheduler._isRender("tree")){var B=scheduler.getSection(D.section_id);if(typeof B.children!="undefined"&&!scheduler.matrix[scheduler._mode].folder_events_available){if(!C){D[scheduler.matrix[scheduler._mode].y_property]=section_id_before}return false}}return true});scheduler.attachEvent("onBeforeDrag",function(D,E,C){var A=scheduler._locate_cell_timeline(C);if(A){var B=scheduler.matrix[scheduler._mode].y_unit[A.y].key;if(typeof scheduler.matrix[scheduler._mode].y_unit[A.y].children!="undefined"&&!scheduler.matrix[scheduler._mode].folder_events_available){return false}}if(scheduler._isRender("tree")){ev=scheduler.getEvent(D);section_id_before=B||ev[scheduler.matrix[scheduler._mode].y_property]}return true});scheduler._getArrayToDisplay=function(C){var A=[];var B=function(G,D){var F=D||0;for(var E=0;E<G.length;E++){G[E].level=F;if(typeof G[E].children!="undefined"&&typeof G[E].key=="undefined"){G[E].key=scheduler.uid()}A.push(G[E]);if(G[E].open&&G[E].children){B(G[E].children,F+1)}}};B(C);return A};scheduler._getArrayForSelect=function(D,C){var A=[];var B=function(F){for(var E=0;E<F.length;E++){if(scheduler.matrix[C].folder_events_available){A.push(F[E])}else{if(typeof F[E].children=="undefined"){A.push(F[E])}}if(F[E].children){B(F[E].children,C)}}};B(D);return A};scheduler._toggleFolderDisplay=function(E,B,A){var D;var C=function(I,J,G,F){for(var H=0;H<J.length;H++){if((J[H].key==I||F)&&J[H].children){J[H].open=(typeof G!="undefined")?G:!J[H].open;D=true;if(!F&&D){break}}if(J[H].children){C(I,J[H].children,G,F)}}};C(E,scheduler.matrix[scheduler._mode].y_unit_original,B,A);scheduler.matrix[scheduler._mode].y_unit=scheduler._getArrayToDisplay(scheduler.matrix[scheduler._mode].y_unit_original);scheduler.callEvent("onOptionsLoad",[])};scheduler.attachEvent("onCellClick",function(B,E,C,A,D){if(scheduler._isRender("tree")){if(!scheduler.matrix[scheduler._mode].folder_events_available){if(typeof scheduler.matrix[scheduler._mode].y_unit[E].children!="undefined"){scheduler._toggleFolderDisplay(scheduler.matrix[scheduler._mode].y_unit[E].key)}}}});scheduler.attachEvent("onYScaleClick",function(A,C,B){if(scheduler._isRender("tree")){if(typeof C.children!="undefined"){scheduler._toggleFolderDisplay(C.key)}}});scheduler.getSection=function(C){if(scheduler._isRender("tree")){var B;var A=function(E,F){for(var D=0;D<F.length;D++){if(F[D].key==E){B=F[D]}if(F[D].children){A(E,F[D].children)}}};A(C,scheduler.matrix[scheduler._mode].y_unit_original);return B||null}};scheduler.deleteSection=function(C){if(scheduler._isRender("tree")){var A=false;var B=function(E,F){for(var D=0;D<F.length;D++){if(F[D].key==E){F.splice(D,1);A=true}if(A){break}if(F[D].children){B(E,F[D].children)}}};B(C,scheduler.matrix[scheduler._mode].y_unit_original);scheduler.matrix[scheduler._mode].y_unit=scheduler._getArrayToDisplay(scheduler.matrix[scheduler._mode].y_unit_original);scheduler.callEvent("onOptionsLoad",[]);return A}};scheduler.addSection=function(D,B){if(scheduler._isRender("tree")){var A=false;var C=function(G,E,H){if(!B){H.push(G);A=true}else{for(var F=0;F<H.length;F++){if(H[F].key==E&&typeof H[F].children!="undefined"){H[F].children.push(G);A=true}if(A){break}if(H[F].children){C(G,E,H[F].children)}}}};C(D,B,scheduler.matrix[scheduler._mode].y_unit_original);scheduler.matrix[scheduler._mode].y_unit=scheduler._getArrayToDisplay(scheduler.matrix[scheduler._mode].y_unit_original);scheduler.callEvent("onOptionsLoad",[]);return A}};scheduler.openAllSections=function(){if(scheduler._isRender("tree")){scheduler._toggleFolderDisplay(1,true,true)}};scheduler.closeAllSections=function(){if(scheduler._isRender("tree")){scheduler._toggleFolderDisplay(1,false,true)}};scheduler.openSection=function(A){if(scheduler._isRender("tree")){scheduler._toggleFolderDisplay(A,true)}};scheduler.closeSection=function(A){if(scheduler._isRender("tree")){scheduler._toggleFolderDisplay(A,false)}};