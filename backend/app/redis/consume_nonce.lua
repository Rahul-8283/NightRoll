if redis.call('EXISTS', KEYS[1]) == 0 then
  return 'missing'
end
if redis.call('HGET', KEYS[1], 'value') ~= ARGV[1] then
  return 'mismatch'
end
if redis.call('HGET', KEYS[1], 'used') == '1' then
  return 'already_used'
end
redis.call('HSET', KEYS[1], 'used', '1')
return 'ok'
