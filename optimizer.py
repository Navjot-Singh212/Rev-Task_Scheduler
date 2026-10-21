import database
from datetime import datetime, timedelta



CATEGORY_ENERGY_DEMAND={
    "deep_work": 8,
    "learning": 7,
    "creative": 7,
    "physical": 6,
    "shallow_work": 4,
    "admin": 3,
    "rest": 1
}


def calculate_effective_priority(base_pri,category,current_energy):
    demand=CATEGORY_ENERGY_DEMAND.get(category.lower(),5)
    energy_deficit=demand-current_energy
    effective=base_pri

    if energy_deficit<=0:
        #meaning the user has enough energy for this task
        if demand>=6 and current_energy>=7:
            effective+=1.5 #high energy so lets boost the priority a lil

    else:
        #the user has less energy than the demand
        if base_pri>=4:  #meaning its an imp task 
            effective-=0.5*energy_deficit   #low penalty~
        else:
            effective-=1.5*energy_deficit   #higher penalty

    return max(1.0,round(effective,1))    # we dont want the effective to be less than 1 if it is 1 we just tell the user to sleep or rest ig

def get_energy_recharge(task_name,category,user_energy):
    #generates a suggestion if the user has low energy for an upcoming high energy task
    demand=CATEGORY_ENERGY_DEMAND.get(category.lower(),5)

    if user_energy<=4 and demand>=7:
        return f"Low Energy {user_energy*10}%: Take a quick 15 min stretch/coffee brake or just relax before '{task_name}'."
    return None


def chunk_large_tasks(task,max_chunk=50,break_min=10,min_orphan=15):

    pref_dur=task["preferred_duration"]

    if pref_dur<=(max_chunk+min_orphan):
        return [task]

    chunks=[]
    remaining_time=pref_dur
    part=1

    while remaining_time>0:
        if max_chunk < remaining_time <= (remaining_time+min_orphan):
            chunk_dur=remaining_time
        else:
            chunk_dur=min(remaining_time,max_chunk)

        chunks.append({'id': f"{task['id']}_p{part}",
            'name': f"{task['name']} (Part {part})",
            'preferred_duration': chunk_dur,
            'min_duration': min(task['min_duration'], chunk_dur),
            'active_duration': chunk_dur,
            'category': task['category'],
            'base_priority': task['base_priority'],
            'effective_priority': task['effective_priority'],
            'nudge': task['nudge'],
            'type': 'flexible',
            'is_chunk': True,
            'break_after': break_min if remaining_time - chunk_dur > 0 else 0
        })
        remaining_time-=chunk_dur
        part+=1

    return chunks

    


def knapsack(flexible_tasks,available_minutes):

    n=len(flexible_tasks)

    if n==0 or available_minutes<=0:
        return []

    
        #a 2d matrix
    dp=[[0]*(available_minutes+1) for _ in range(n+1)]

    for i in range(1,n+1):
        task=flexible_tasks[i-1]
        duration=task['active_duration']
        priority=int(task["effective_priority"]*10)

        # the core logic engine that decides what tasks to take and leave to maximum priority
        for w in range(1,available_minutes+1):
            if duration<=w:
                take_it=priority+dp[i-1][w-duration]

                leave_it=dp[i-1][w]

                dp[i][w]=max(take_it,leave_it)
            else:
                dp[i][w]=dp[i-1][w]


    selected_tasks=[]
    w=available_minutes


    #to backtrack to see what tasks were actually selected
    for i in range(n,0,-1):
        if dp[i][w]!=dp[i-1][w]:
            task=flexible_tasks[i-1]
            selected_tasks.append(task)
            w-=task['active_duration']    #subtract the duration from the remaining

    return selected_tasks


def apply_sorting_strategy(task_list,strategy):
    "sorts chosen tasks based on different task tackling strategy, i wanted that we let the user choose his/her psychological strategies"
    if strategy=="snowball" and len(task_list)>1:
        task_list.sort(key=lambda x:x["effective_priority"],reverse=True)
        warmup_task=min(task_list,key=lambda x: x['active_duration'])
        task_list.remove(warmup_task)
        task_list.insert(0,warmup_task)
    elif strategy=="quick_wins":
        task_list.sort(key=lambda x:(x['active_duration'], -x["effective_priority"]))
    else:    #the third one is eat_the_frog
        task_list.sort(key=lambda x:x["effective_priority"],reverse=True)

    return task_list

def render_tasks_to_timeline(task_list,current_time,timeline,buffer_minutes,gap_minutes=None):
        #Appends scheduled tasks, recharge breaks, and other breaks between tasks yk because the user isn't a machnine it cannot do tasks non-stop
        for task in task_list:
            #injects recharge block if energy is low
            if task.get('nudge') and (gap_minutes is None or gap_minutes>= task['active_duration']+15):
                break_end=current_time+timedelta(minutes=15)
                timeline.append({'time_slot': f"{current_time.strftime('%I:%M %p')} - {break_end.strftime('%I:%M %p')}",
                'name': "⚡ Energy Recharge (Coffee / Quick Walk etc..)  ⚡",
                'type': 'Break',
                'priority': 'N/A'})
                current_time=break_end

            end_time=current_time+timedelta(minutes=task['active_duration'])
            duration_label=f"{task['active_duration']}m"
            if task['active_duration']<task["preferred_duration"]:
                duration_label+=" (Sliced)"

            timeline.append({'time_slot': f"{current_time.strftime('%I:%M %p')} - {end_time.strftime('%I:%M %p')}",
            'name': f"{task['name']} [{duration_label}]",
            'type': 'Flexible Task',
            'priority': f"Base: {task['base_priority']} ➔ Eff: {task['effective_priority']}",
            'nudge': task['nudge']})

            if task.get("break_after",0)>0:
                current_time=end_time
                break_end=current_time=timedelta(minutes=task['break_after'])
                timeline.append({
                'time_slot': f"{current_time.strftime('%I:%M %p')} - {break_end.strftime('%I:%M %p')}",
                'name': "☕ Short Rest / Stretch",
                'type': 'Break',
                'priority': 'N/A'
            })
                current_time=break_end
            else:
                current_time=end_time+timedelta(minutes=buffer_minutes)

        return current_time


def generate_unified_schedule(current_energy=5,buffer_minutes=5,strategy="eat_the_frog"):
    "adds flexible tasks around fixed tasks based on the strategy the user chooses"
    all_tasks=database.get_pending_tasks()
    now=datetime.now()

    flexible_tasks=[]
    anchors=[]

    for task in all_tasks:
        if task[8]: #Anchor (fixed time task)
            time_parts=list(map(int,task[8].split(":")))
            anchor_dt=now.replace(hour=time_parts[0],minute=time_parts[1],second=0,microsecond=0)
            if anchor_dt>now:
                anchors.append({'id': task[0], 'name': task[1], 'duration': task[2],
                    'category': task[4], 'start_time': anchor_dt, 'type': 'anchor'})

        else:
            #Flexible tasks
            eff_prio=calculate_effective_priority(task[5],task[4],current_energy=current_energy)
            nudge=get_energy_recharge(task[1],task[4],current_energy)

            raw_task={'id': task[0], 'name': task[1],
                'preferred_duration': task[2], 'min_duration': task[3],
                'active_duration': task[2], 'category': task[4], 
                'base_priority': task[5], 'effective_priority': eff_prio, 
                'nudge': nudge, 'type': 'flexible'}
            flexible_tasks.extend(chunk_large_tasks(raw_task))

    anchors.sort(key=lambda x: x["start_time"])
    timeline=[]
    current_time=now

    for anchor in anchors:
        gap_minutes=int((anchor['start_time']-current_time).total_seconds()//60)

        if gap_minutes>0 and flexible_tasks:
            for ft in flexible_tasks:
                if ft["preferred_duration"]>gap_minutes>=ft['min_duration']:
                    ft["active_duration"]=ft["min_duration"]
                else:
                    ft["active_duration"]=ft["preferred_duration"]

            chosen=knapsack(flexible_tasks,gap_minutes)
            chosen=apply_sorting_strategy(chosen,strategy)
            current_time=render_tasks_to_timeline(chosen,current_time,timeline,buffer_minutes,gap_minutes)
            
            for task in chosen:
                flexible_tasks.remove(task)

        if current_time<anchor["start_time"]:
            current_time=anchor["start_time"]

        anchor_end=anchor["start_time"]+timedelta(minutes=anchor["duration"])
        timeline.append({
            'time_slot': f"{anchor['start_time'].strftime('%I:%M %p')} - {anchor_end.strftime('%I:%M %p')}",
            'name': f"📌 {anchor['name']} (Fixed Event)",
            'type': 'Anchor',
            'priority': 'LOCKED',
            'nudge': None
        })
        current_time=anchor_end+timedelta(minutes=buffer_minutes)


    #scheduling remaining flexible tasks post anchor
    if flexible_tasks:
        for ft in flexible_tasks:
            ft['active_duration']=ft['preferred_duration']

        chosen_remaining=knapsack(flexible_tasks,240)    #this is time left after all the anchors or fixed events are done so we have free time now
        "i have to update this 240 later  when i integrate user's bedtime or non-working hours"
        chosen_remaining=apply_sorting_strategy(chosen_remaining,strategy=strategy)
        current_time=render_tasks_to_timeline(chosen_remaining,current_time,timeline,buffer_minutes)
        #no gap minutes will be needed here since we are done with the anchors
        
        
        return timeline



if __name__=="__main__":
    print("Initialising the Enegry Aware Knapsack optimiser~")

    user_energy = 8
    test_strategy = "snowball"
    print(f"🔋 Current User Energy: {user_energy}/10")
    print(f"Selected strategy: {test_strategy.replace("_"," ").title()}\n")

    schedule=generate_unified_schedule(user_energy,strategy=test_strategy)
    print("YOUR UNIFIED SCHEDULE:")
    for item in schedule:
        nudge_str=f"{item['nudge']}" if item.get("nudge") else ""
        print(f"[{item["time_slot"]}] {item["name"]} | Priority: {item["priority"]}{nudge_str}")
