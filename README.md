# ast_utils
A collection of python abstract syntax tree utilities useful when searching for needles in haystacks

This suite of tools was part of a larger suite that helped me determine every single database call in every openstack service api call.

I focused on building tools that let me see line numbers, assignments, functions called, modules imported etc.  The tricky part, at least for OpenStack, was figuring out where exactly the library they said they were importing was actually located on disk.  I excised a lot of the code that ran that portion of the system, as it's not terribly applicable for a general solution, but I thought I'd mention it if anyone wonders.

