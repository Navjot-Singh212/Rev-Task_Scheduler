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

if __name__=="__main__":
    print("Initialising the Knapsack optimiser~")
    best_tasks,fixed_tasks=knapsack(120)

    print("Fixed tasks:")
    for m in fixed_tasks:
        print(f"Locked {m} at {m[8]}")

    print("Flexible tasks:")
    for m in best_tasks:
        print(f"Do {m[1]} (Duration : {m[2]}m and priority : {m[5]})")

    
