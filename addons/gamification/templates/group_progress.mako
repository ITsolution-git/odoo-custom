<% extends 'base.mako' %>

<% block body %>
	% for planline in planlines_boards: 
        <table width="100%" border="1">
        	<tr>
        		<th colspan="4">${planline.goal_type.name}</th>
        	</tr>
        	<tr>
	            <th>#</th>
	            <th>Person</th>
	            <th>Completeness</th>
	            <th>Current</th>
	        </tr>
	        % for idx, goal in planline.board_goals:
	            <tr
	                % if goal.completeness >= 100:
	                    style="font-weight:bold;"
	                % endif
	                >
	                <td>${idx+1}</td>
	                <td>${goal.user_id.name}</td>
	                <td>${goal.completeness}%</td>
	                <td>${goal.current}/${goal.target_goal}</td>
	            </tr>
	        % endfor
        </table>

        <br/><br/>

    % endfor
<% endblock %>