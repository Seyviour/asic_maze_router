from ast import Compare
import heapq
import itertools
import dataclasses
from collections import defaultdict
#from typing_extensions import Self
#from re import S


# @dataclasses.dataclass(order=True)
# class SearchNode:
#     sort_index: int = dataclasses.field(init=False, repr=False)
#     location: tuple
#     cost: int
#     id: int
#     predecessor_id: int
#     predecessor_direction: int

#     def __post_init__(self):
#         self.sort_index = self.cost

class MazeRouter():
    def __init__(self): 

        self.paths = {}
        #DIRECTION CONSTANTS
        self.ROOT = 0
        self.RIGHT = 1
        self.LEFT = 2
        self.UP = 3
        self.DOWN = 4
        self.LAYERUP = 5
        self.LAYERDOWN = 6


    def grid_from_file(self, filename, format='cousera'):

        with open(filename, 'r') as f: 
            grid_data = next(f)
            grid_data = [int(x) for x in grid_data.strip().split()]
            C, R, bend_penalty, via_penalty = grid_data

            layer1 = [[] for _ in range(R)]
            layer2 = [[] for _ in range(R)]

            for r in range(R):
                this_row = next(f)
                this_row = [int(x) for x in this_row.strip().split()]

                layer1[r] = this_row
            
            for r in range(R):
                this_row = next(f)
                this_row = [int(x) for x in this_row.strip().split()]

                layer2[r] = this_row

            self.R = R
            self.C = C
            self.numrows = R
            self.numcols = C
            self.VIA_PENALTY = via_penalty
            self.BEND_PENALTY = bend_penalty
            self.grid = [layer1, layer2]
    
    def netlist_from_file(self, filename, format = 'coursera'):

        with open(filename, 'r') as f:

            no_nets = next(f)
            no_nets = int(no_nets.strip())

            netlist = [0] * no_nets

            for i in range(no_nets):

                this_net = next(f)

                this_net = [int(x) for x in this_net.strip().split()]

                #adjust net_id to 0-index
                this_net[0] -= 1
                this_net[1] -= 1
                this_net[4] -= 1

                net_id, l1, x1, y1, l2, x2, y2 = this_net

                pin1 = (l1,x1,y1)
                pin2 = (l2,x2,y2)

                netlist[net_id] = (pin1, pin2)
            
            self.netlist = netlist
        
    def mark_pin_cells_as_unusable(self):
        for idx, net in enumerate(self.netlist):
            
            pin1_location, pin2_location = net

            l1, c1, r1 = pin1_location
            l2, c2, r2 = pin2_location

            self.grid[l1][r1][c1] = -1
            self.grid[l2][r2][c2] = -1



    def _set_cell_cost(self, net, cost):
        l, c, r = net
        self.grid[l][r][c] = cost


    def _unlock_for_routing(self, net_id):

        net = self.netlist[net_id]
        pin1_location, pin2_location = net

        self._set_cell_cost(pin1_location, 1)
        self._set_cell_cost(pin2_location, 1)


    
    def _get_node_cost(self, node):
        l, x, y = node

        #yeah, the order of the y and x weirds me out too, lol. iiwis
        return self.grid[l][y][x]


    def _get_neighbours_and_direction(self, node):

        """
        direction is reversed direction
        """
        l, c, r = node
        
        #right
        if c < self.C-1: 
            yield (l, c+1, r), self.LEFT
        
        #left
        if c > 0:
            yield (l, c-1, r), self.RIGHT
        
        #up
        if r < self.R-1:
            yield (l, c, r+1), self.DOWN
        
        #down
        if r > 0:
            yield (l, c, r-1), self.UP
        
        #layerup
        if l == 0:
            yield (1, c, r), self.LAYERDOWN
        
        #layerdown
        if l == 1:
            yield (0, c, r), self.LAYERUP
    
    def _get_unblocked_neighbours_and_cost(self, node):
        unusable = [-1, -2]

        for node, direction in self._get_neighbours_and_direction(node):
            if (cost:= self._get_node_cost(node)) not in unusable:
                yield node, cost, direction

    def _get_direction(self):
        return 


    # @dataclasses.dataclass(order=True)
    # class SearchNode:
    #     location: tuple
    #     #priority: float
    #     cost: int
    #     id: int
    #     predecessor_id: int
    #     predecessor_direction: int

    #     def __post_init__(self):
    #         self.sort_index = -self.cost
    @dataclasses.dataclass(order=True)
    class SearchNode:
        sort_index: int = dataclasses.field(init=False, repr=False)
        location: tuple
        cost: int
        id: int
        predecessor_id: int
        predecessor_direction: int
        est_distance: int = dataclasses.field(init=True, repr=False, default=0)

        def __post_init__(self):
            self.sort_index = self.cost + self.est_distance


    def _cleanup_and_block(self, net_id, find, entrydict):
        path = []

        curr = find
        while curr and True:
            path.append(curr.location)
            l,x,y = curr.location
            self.grid[l][y][x] = -1
            if curr.predecessor_direction == self.ROOT:
                break
            else:
                curr = entrydict[curr.predecessor_id]

        path.reverse()
        print(net_id, len(path))
        self.paths[net_id] = path

        
    def _A_distance_estimator(self, location1, location2):
        l1, c1, r1 = location1
        l2, c2, r2 = location2

        dc = abs(c2-c1)
        dr = abs(r2-r1)

        est = 0

        if (dc == 0) or (dr == 0):
            est += dc + dr
        else:
            est += dc + dr + self.BEND_PENALTY
        
        if l2 != l1:
            est += self.VIA_PENALTY
        
        return est


    def find_path(self, net_id):

        self._unlock_for_routing(net_id)

        net = self.netlist[net_id]
        id_generator = itertools.count()
        
        #REMOVED = 0

        dj_heap = []

        source_location, target_location = net
        source_cost = self._get_node_cost(source_location)
        source_id = next(id_generator)

        start_node = self.SearchNode(source_location,
                                    source_cost,
                                    source_id, 
                                    source_id, 
                                    self.ROOT,
                                    0)

        entries = {0: start_node}
        heapq.heappush(dj_heap, start_node)
        find = None

        a_stop = 0 
        b_stop = 0

        lows = {}


        while dj_heap:
            this_node = heapq.heappop(dj_heap)

            #update find

            if this_node.location == target_location:
                if find is None or this_node.cost > find.cost:
                    find = this_node
                    #break
            elif this_node.location == source_location and a_stop != 0:
                continue

            if find and this_node.cost > find.cost:
                continue

            if not find: 
                a_stop += 1
            
            else:
                b_stop += 1
                if b_stop >= a_stop * 0.01: 
                    break

            
            predecessor_id = this_node.id

            ada_id = this_node.predecessor_id
            predecessor_location = entries[ada_id].location

            for next_node in self._get_unblocked_neighbours_and_cost(this_node.location):

                location, cost, direction = next_node

                if location == predecessor_location:
                    continue

                id = next(id_generator)

                cost += this_node.cost

                if direction == self.LAYERDOWN or direction == self.LAYERDOWN:
                    cost += self.VIA_PENALTY
                elif direction != this_node.predecessor_direction:
                    cost += self.BEND_PENALTY

                
                if location not in lows or cost < lows[location]: 
                    lows[location] = cost
                else:
                    continue

                est_distance = self._A_distance_estimator(location, target_location)
                
                succ_search = self.SearchNode(location=location,
                                             cost = cost,
                                             id = id,
                                             predecessor_id=predecessor_id,
                                             predecessor_direction=direction,
                                             est_distance=est_distance)

                entries[id] = succ_search

                #print(succ_search < this_node)
                heapq.heappush(dj_heap, succ_search)

        return find, entries

    def route_and_clean_up(self, net_id):
        find, entries = self.find_path(net_id)
        
        self._cleanup_and_block(net_id, find, entries)

        del find
        del entries
    
    def route_all(self):

        idxs = [i for i in range(len(self.netlist))]
        netlist_copy = list(self.netlist)

        netlist_copy = list(zip(idxs, netlist_copy))
        netlist_copy.sort(key = lambda x: self._A_distance_estimator(x[1][0], x[1][1]))

        # for net_id in range(0, len(self.netlist)):
        #     self.route_and_clean_up(net_id)
        #netlist_copy.reverse()
        for net_id, _ in netlist_copy:
            print(net_id)
            self.route_and_clean_up(net_id)

    def write_results(self, filename, format='coursera'):
        with open(filename, 'w') as f:
            line1 = f"{len(self.netlist)} \n"
            f.write(line1)
            for net_id in range(0, len(self.netlist)):
                f.write(str(net_id+1) + "\n")
                
                
                path = self.paths[net_id]

                if path: 
                    l, c, r = path[0]
                    f.write(f"{l+1} {c} {r} \n")

                    for idx, cell in enumerate(path):
                        if idx == 0:
                            continue
                        
                        l, c, r = cell
                        l_, c_, r_ = path[idx-1]

                        if l != l_:
                            f.write(f"3 {c_} {r_} \n")
                        
                        f.write(f"{l+1} {c} {r} \n")
                
        
                f.write("0 \n")

                    










if __name__ == "__main__":
    this_router = MazeRouter()
    this_router.grid_from_file(r"industry1.grid")
    this_router.netlist_from_file(r"industry1.nl")
    this_router.mark_pin_cells_as_unusable()
    #this_router.find_path(0)
    #this_router.route_and_clean_up(0)
    this_router.route_all()
    this_router.write_results("industry1")
    #route = this_router.paths[0]

    location1 = (0,0,0)
    location2 = (0,1,1)
    print("myname")