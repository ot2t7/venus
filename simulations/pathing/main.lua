local polylines = require("geometry2d.polylines");
local polylinesOffsets = require("geometry2d.polyline_offset");
local polygonUtils = require("geometry2d.polygons");

-- Turns an object in format {{x, y}, {x, y}} into {x,y, x,y}
local function expandGeometry(obj)
    local result = {};
    for _i, point in ipairs(obj) do
        table.insert(result, point[1]);
        table.insert(result, point[2]);
    end
    return result;
end

-- Finds the minimum and maximum X and Y values possible on the polygon.
-- Returns {smallestX, biggestX, smallestY, biggestY}
local function getLimits(polygon)
    local _, smallestX = polylines.to_point(-10e10, 0, polygon, 1, #polygon, 1, 2);
    local _, biggestX = polylines.to_point(10e10, 0, polygon, 1, #polygon, 1, 2);

    local _, _, smallestY = polylines.to_point(0, -10e10, polygon, 1, #polygon, 1, 2);
    local _, _, biggestY = polylines.to_point(0, 10e10, polygon, 1, #polygon, 1, 2);
    return { smallestX, biggestX, smallestY, biggestY };
end

-- Creates a line from last point in the currentPolyLine to the pointToMarch,
-- but stops the line short if it stops intersecting the polygon, and goes
-- farther than the increment parameter away from it.
local function march(increment, polygon, currentPolyLine, pointToMarch)
    local currPoint = { currentPolyLine[#currentPolyLine][1], currentPolyLine[#currentPolyLine][2] };
    local distanceToNext = math.sqrt(math.pow(currPoint[1] - pointToMarch[1], 2) +
        math.pow(currPoint[2] - pointToMarch[2], 2));
    local xNorm = (pointToMarch[1] - currPoint[1]) / distanceToNext;
    local yNorm = (pointToMarch[2] - currPoint[2]) / distanceToNext;

    while true do
        -- This recalculation is necessary, as currPoint changes.
        distanceToNext = math.sqrt(math.pow(currPoint[1] - pointToMarch[1], 2) +
            math.pow(currPoint[2] - pointToMarch[2], 2));

        if distanceToNext <= increment then
            currPoint = pointToMarch;
            break;
        else
            local proposedPoint = { currPoint[1] + xNorm * increment, currPoint[2] + yNorm * increment };
            local distanceFromPolygon = polylines.to_point(proposedPoint[1], proposedPoint[2], polygon, 1, #polygon, 1, 2);
            if polygonUtils.inside(proposedPoint[1], proposedPoint[2], polygon, 1, #polygon, 1, 2) or distanceFromPolygon < increment then
                currPoint = proposedPoint;
            else
                break;
            end
        end
    end

    table.insert(currentPolyLine, currPoint);
end

-- Finds the minimum and maximum X values possible on a y = index
-- line across the polygon
-- Returns {smallestX, biggestX}
local function getHorizontalLimits(polygon, index)
    index = index + 0.01; -- This to prevent intercepting with any parallel lines, and any vertexes.
    local slicePoint1 = { -10e10, index };
    local slicePoint2 = { 10e10, index };
    local intersects = {};
    for i, point in ipairs(polygon) do
        if i < #polygon then
            local next = polygon[i + 1];
            local x1 = slicePoint1[1];
            local x2 = slicePoint2[1];
            local x3 = point[1];
            local x4 = next[1];
            local y1 = slicePoint1[2];
            local y2 = slicePoint2[2];
            local y3 = point[2];
            local y4 = next[2];

            -- https://en.wikipedia.org/wiki/Line%E2%80%93line_intersection#Given_two_points_on_each_line_segment
            local t1 = (x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4);
            local t2 = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4);
            local t = t1 / t2;

            local u1 = (x1 - x3) * (y1 - y2) - (y1 - y3) * (x1 - x2);
            local u2 = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4);
            local u = u1 / u2;

            if (t >= 0 and t <= 1) and (u >= 0 and u <= 1) then
                table.insert(intersects, x1 + t * (x2 - x1));
            end
        end
    end
    table.sort(intersects);
    return { intersects[1], intersects[#intersects] };
end


local EXPLORE_RIGHT = 0;
local PIVOT_RIGHT = 1;
local EXPLORE_LEFT = 2;
local PIVOT_LEFT = 3;

local function generateSearchPath(searchArea, cameraSize)
    local polyResult = {};
    local smallestX, biggestX, smallestY, biggestY = unpack(getLimits(searchArea));
    local yTraversed = smallestY;
    local startX = getHorizontalLimits(searchArea, yTraversed)[1];
    table.insert(polyResult, { startX, yTraversed });

    local nextState = EXPLORE_RIGHT;
    while true do
        if nextState == EXPLORE_RIGHT then
            local biggestX = getHorizontalLimits(searchArea, yTraversed)[2];
            table.insert(polyResult, { biggestX, yTraversed });

            nextState = PIVOT_RIGHT;
        elseif nextState == PIVOT_RIGHT then
            yTraversed = yTraversed + cameraSize * 2;
            if yTraversed >= biggestY then break end


            local biggestX = getHorizontalLimits(searchArea, yTraversed)[2];
            table.insert(polyResult, { biggestX, yTraversed });

            nextState = EXPLORE_LEFT;
        elseif nextState == EXPLORE_LEFT then
            local smallestX = getHorizontalLimits(searchArea, yTraversed)[1];
            table.insert(polyResult, { smallestX, yTraversed });

            nextState = PIVOT_LEFT;
        elseif nextState == PIVOT_LEFT then
            yTraversed = yTraversed + cameraSize * 2;
            if yTraversed >= biggestY then break end

            local smallestX = getHorizontalLimits(searchArea, yTraversed)[1];
            table.insert(polyResult, { smallestX, yTraversed });

            nextState = EXPLORE_RIGHT;
        end

        print(polyResult[#polyResult][1], polyResult[#polyResult][2])
    end

    return polyResult;
end

local function generateSearchPath2(searchArea, cameraSize)
    local polyResult = {};
    local touchCornerOffset = math.sqrt((CameraSize * CameraSize) / 2);
    local currentOffset = touchCornerOffset;
    local centroidX, centroidY = polygonUtils.centroid(searchArea, 1, #searchArea, 1, 2);
    local distanceToCentroid = math.sqrt(math.pow(searchArea[1][1] - centroidX, 2) + math.pow(searchArea[1][2] - centroidY, 2));
    local increments = cameraSize * 1.5;
    local tolerance = distanceToCentroid - increments * 2;

    while currentOffset < tolerance do
        local offsetted = polylinesOffsets.offset(searchArea, currentOffset, searchArea, 1, #searchArea, 1, 2);
        for _, point in ipairs(offsetted) do
            table.insert(polyResult, point);
        end
        currentOffset = currentOffset + increments;
    end
    --table.insert(polyResult, {centroidX, centroidY});
    return polyResult;
end

local function pointOnLine(line, distance)
    for i, point in ipairs(line) do
        if #line == i then
            return { 0, 0 };
        end

        local next = line[i + 1];
        local distanceToNext = math.sqrt(math.pow(point[1] - next[1], 2) + math.pow(point[2] - next[2], 2));
        local xNorm = (next[1] - point[1]) / distanceToNext;
        local yNorm = (next[2] - point[2]) / distanceToNext;

        if (distance <= distanceToNext) then
            return { point[1] + (xNorm * distance), point[2] + (yNorm * distance) }
        else
            distance = distance - distanceToNext;
        end
    end
end

function love.load()
    -- Some constants
    CameraSize        = 30;
    TouchCornerOffset = math.sqrt((CameraSize * CameraSize) / 2);
    DroneSpeed        = 3;
    DroneAmountMoved  = 0;
    DronePos          = { 0, 0 };
    AreaSearched      = {};

    SearchArea        = { {100, 100}, {500, 150}, {500, 400}, {300, 500}, {80, 300}, {100, 100} }

    SearchPath        = generateSearchPath2(SearchArea, CameraSize);
end

function love.update()
    -- Move the drone
    DronePos = pointOnLine(SearchPath, DroneAmountMoved);
    DroneAmountMoved = DroneAmountMoved + DroneSpeed;

    -- Save a snapshot of what it sees, to show what we have searched overall
    table.insert(AreaSearched, { DronePos[1], DronePos[2] });
end

function love.draw()
    -- Draw the search area
    love.graphics.setColor(1, 1, 1);
    love.graphics.setColor(1, 1, 1);
    love.graphics.polygon("fill", expandGeometry(SearchArea));

    -- Draw the calculated search path
    love.graphics.setColor(0, 0, 1);
    love.graphics.setLineWidth(4);
    love.graphics.line(expandGeometry(SearchPath));

    -- Draw all the circle mass which represents what we have searched so far
    love.graphics.setColor(1, 0, 0);
    for _i, p in ipairs(AreaSearched) do
        love.graphics.circle("fill", p[1], p[2], CameraSize, 100);
    end

    -- Draw the drone
    love.graphics.setColor(0, 0, 0);
    love.graphics.setPointSize(5);
    love.graphics.points(DronePos[1], DronePos[2]);
end
