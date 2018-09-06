import bpy, re
from bpy.props import *
from .common import *
from .node_connections import *
from .node_arrangements import *
from . import lib

modifier_type_items = (
        ('INVERT', 'Invert', '', 'MODIFIER', 0),
        ('RGB_TO_INTENSITY', 'RGB to Intensity', '', 'MODIFIER', 1),
        ('COLOR_RAMP', 'Color Ramp', '', 'MODIFIER', 2),
        ('RGB_CURVE', 'RGB Curve', '', 'MODIFIER', 3),
        ('HUE_SATURATION', 'Hue Saturation', '', 'MODIFIER', 4),
        ('BRIGHT_CONTRAST', 'Brightness Contrast', '', 'MODIFIER', 5),
        ('MULTIPLIER', 'Multiplier', '', 'MODIFIER', 6),
        #('GRAYSCALE_TO_NORMAL', 'Grayscale To Normal', ''),
        #('MASK', 'Mask', ''),
        )

can_be_expanded = {
        'INVERT', 
        'COLOR_RAMP',
        'RGB_CURVE',
        'HUE_SATURATION',
        'BRIGHT_CONTRAST',
        'MULTIPLIER',
        }

def remove_modifier_start_end_nodes(m, tree):

    start_rgb = tree.nodes.get(m.start_rgb)
    start_alpha = tree.nodes.get(m.start_alpha)
    end_rgb = tree.nodes.get(m.end_rgb)
    end_alpha = tree.nodes.get(m.end_alpha)
    frame = tree.nodes.get(m.frame)

    tree.nodes.remove(start_rgb)
    tree.nodes.remove(start_alpha)
    tree.nodes.remove(end_rgb)
    tree.nodes.remove(end_alpha)
    tree.nodes.remove(frame)

def add_modifier_nodes(m, tree, ref_tree=None):

    tl = m.id_data.tl
    nodes = tree.nodes
    links = tree.links

    match1 = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]\.modifiers\[(\d+)\]', m.path_from_id())
    match2 = re.match(r'tl\.channels\[(\d+)\]\.modifiers\[(\d+)\]', m.path_from_id())
    if match1:
        root_ch = tl.channels[int(match1.group(2))]
    elif match2: 
        root_ch = tl.channels[int(match2.group(1))]
    else: return None

    # Get non color flag
    non_color = root_ch.colorspace == 'LINEAR'

    # Remove previous start and end if ref tree is passed
    if ref_tree:
        remove_modifier_start_end_nodes(m, ref_tree)

    # Create new pipeline nodes
    start_rgb = new_node(tree, m, 'start_rgb', 'NodeReroute', 'Start RGB')
    end_rgb = new_node(tree, m, 'end_rgb', 'NodeReroute', 'End RGB')
    start_alpha = new_node(tree, m, 'start_alpha', 'NodeReroute', 'Start Alpha')
    end_alpha = new_node(tree, m, 'end_alpha', 'NodeReroute', 'End Alpha')
    frame = new_node(tree, m, 'frame', 'NodeFrame')

    start_rgb.parent = frame
    start_alpha.parent = frame
    end_rgb.parent = frame
    end_alpha.parent = frame

    # Link new nodes
    links.new(start_rgb.outputs[0], end_rgb.inputs[0])
    links.new(start_alpha.outputs[0], end_alpha.inputs[0])

    # Create the nodes
    if m.type == 'INVERT':

        if ref_tree:
            invert_ref = ref_tree.nodes.get(m.invert)

        invert = new_node(tree, m, 'invert', 'ShaderNodeGroup', 'Invert')

        if ref_tree:
            copy_node_props(invert_ref, invert)
            ref_tree.nodes.remove(invert_ref)
        else:
            if root_ch.type == 'VALUE':
                invert.node_tree = lib.get_node_tree_lib(lib.MOD_INVERT_VALUE)
            else: invert.node_tree = lib.get_node_tree_lib(lib.MOD_INVERT)

            if BLENDER_28_GROUP_INPUT_HACK:
                duplicate_lib_node_tree(invert)

        links.new(start_rgb.outputs[0], invert.inputs[0])
        links.new(invert.outputs[0], end_rgb.inputs[0])

        links.new(start_alpha.outputs[0], invert.inputs[1])
        links.new(invert.outputs[1], end_alpha.inputs[0])

        frame.label = 'Invert'
        invert.parent = frame

    elif m.type == 'RGB_TO_INTENSITY':

        if ref_tree:
            rgb2i_ref = ref_tree.nodes.get(m.rgb2i)

        rgb2i = new_node(tree, m, 'rgb2i', 'ShaderNodeGroup', 'RGB to Intensity')

        if ref_tree:
            copy_node_props(rgb2i_ref, rgb2i)
            ref_tree.nodes.remove(rgb2i_ref)
        else:
            rgb2i.node_tree = lib.get_node_tree_lib(lib.MOD_RGB2INT)

            if BLENDER_28_GROUP_INPUT_HACK:
                duplicate_lib_node_tree(rgb2i)

            if root_ch.type == 'RGB':
                m.rgb2i_col = (1.0, 0.0, 1.0, 1.0)
        
        links.new(start_rgb.outputs[0], rgb2i.inputs[0])
        links.new(start_alpha.outputs[0], rgb2i.inputs[1])

        links.new(rgb2i.outputs[0], end_rgb.inputs[0])
        links.new(rgb2i.outputs[1], end_alpha.inputs[0])

        if non_color:
            rgb2i.inputs['Gamma'].default_value = 1.0
        else: rgb2i.inputs['Gamma'].default_value = 1.0/GAMMA

        if BLENDER_28_GROUP_INPUT_HACK:
            match_group_input(rgb2i, 'Gamma')
            #inp = rgb2i.node_tree.nodes.get('Group Input')
            #if inp.outputs[3].links[0].to_socket.default_value != rgb2i.inputs['Gamma'].default_value:
            #    inp.outputs[3].links[0].to_socket.default_value = rgb2i.inputs['Gamma'].default_value

        frame.label = 'RGB to Intensity'
        rgb2i.parent = frame

    elif m.type == 'COLOR_RAMP':

        if ref_tree:
            color_ramp_alpha_multiply_ref = ref_tree.nodes.get(m.color_ramp_alpha_multiply)
            color_ramp_ref = ref_tree.nodes.get(m.color_ramp)
            color_ramp_linear_ref = ref_tree.nodes.get(m.color_ramp_linear)
            color_ramp_mix_alpha_ref = ref_tree.nodes.get(m.color_ramp_mix_alpha)
            color_ramp_mix_rgb_ref = ref_tree.nodes.get(m.color_ramp_mix_rgb)

        color_ramp_alpha_multiply = new_node(tree, m, 'color_ramp_alpha_multiply', 'ShaderNodeMixRGB', 
                'ColorRamp Alpha Multiply')
        color_ramp = new_node(tree, m, 'color_ramp', 'ShaderNodeValToRGB', 'ColorRamp')
        color_ramp_linear = new_node(tree, m, 'color_ramp_linear', 'ShaderNodeGamma', 'ColorRamp')
        color_ramp_mix_alpha = new_node(tree, m, 'color_ramp_mix_alpha', 'ShaderNodeMixRGB', 'ColorRamp Mix Alpha')
        color_ramp_mix_rgb = new_node(tree, m, 'color_ramp_mix_rgb', 'ShaderNodeMixRGB', 'ColorRamp Mix RGB')

        if ref_tree:
            copy_node_props(color_ramp_alpha_multiply_ref, color_ramp_alpha_multiply)
            copy_node_props(color_ramp_ref, color_ramp)
            copy_node_props(color_ramp_linear_ref, color_ramp_linear)
            copy_node_props(color_ramp_mix_alpha_ref, color_ramp_mix_alpha)
            copy_node_props(color_ramp_mix_rgb_ref, color_ramp_mix_rgb)

            ref_tree.nodes.remove(color_ramp_alpha_multiply_ref)
            ref_tree.nodes.remove(color_ramp_ref)
            ref_tree.nodes.remove(color_ramp_mix_alpha_ref)
            ref_tree.nodes.remove(color_ramp_mix_rgb_ref)
        else:

            color_ramp_alpha_multiply.inputs[0].default_value = 1.0
            color_ramp_alpha_multiply.blend_type = 'MULTIPLY'

            color_ramp_mix_alpha.inputs[0].default_value = 1.0

            color_ramp_mix_rgb.inputs[0].default_value = 1.0

            if root_ch.colorspace == 'SRGB':
                color_ramp_linear.inputs[1].default_value = 1.0/GAMMA
            else: color_ramp_linear.inputs[1].default_value = 1.0

            # Set default color
            color_ramp.color_ramp.elements[0].color = (0,0,0,0)

        links.new(start_rgb.outputs[0], color_ramp_alpha_multiply.inputs[1])
        links.new(start_alpha.outputs[0], color_ramp_alpha_multiply.inputs[2])
        links.new(color_ramp_alpha_multiply.outputs[0], color_ramp.inputs[0])
        #links.new(start_rgb.outputs[0], color_ramp.inputs[0])
        #links.new(color_ramp.outputs[0], end_rgb.inputs[0])
        links.new(start_rgb.outputs[0], color_ramp_mix_rgb.inputs[1])
        #links.new(color_ramp.outputs[0], color_ramp_mix_rgb.inputs[2])
        links.new(color_ramp.outputs[0], color_ramp_linear.inputs[0])
        links.new(color_ramp_linear.outputs[0], color_ramp_mix_rgb.inputs[2])
        links.new(color_ramp_mix_rgb.outputs[0], end_rgb.inputs[0])

        links.new(start_alpha.outputs[0], color_ramp_mix_alpha.inputs[1])
        links.new(color_ramp.outputs[1], color_ramp_mix_alpha.inputs[2])
        links.new(color_ramp_mix_alpha.outputs[0], end_alpha.inputs[0])

        frame.label = 'Color Ramp'
        color_ramp.parent = frame
        color_ramp_linear.parent = frame
        color_ramp_alpha_multiply.parent = frame
        color_ramp_mix_alpha.parent = frame
        color_ramp_mix_rgb.parent = frame

    elif m.type == 'RGB_CURVE':

        if ref_tree:
            rgb_curve_ref = ref_tree.nodes.get(m.rgb_curve)

        rgb_curve = new_node(tree, m, 'rgb_curve', 'ShaderNodeRGBCurve', 'RGB Curve')

        if ref_tree:
            copy_node_props(rgb_curve_ref, rgb_curve)
            ref_tree.nodes.remove(rgb_curve_ref)

        links.new(start_rgb.outputs[0], rgb_curve.inputs[1])
        links.new(rgb_curve.outputs[0], end_rgb.inputs[0])

        frame.label = 'RGB Curve'
        rgb_curve.parent = frame

    elif m.type == 'HUE_SATURATION':

        if ref_tree:
            huesat_ref = ref_tree.nodes.get(m.huesat)

        huesat = new_node(tree, m, 'huesat', 'ShaderNodeHueSaturation', 'Hue Saturation')

        if ref_tree:
            copy_node_props(huesat_ref, huesat)
            ref_tree.nodes.remove(huesat_ref)

        links.new(start_rgb.outputs[0], huesat.inputs[4])
        links.new(huesat.outputs[0], end_rgb.inputs[0])

        frame.label = 'Hue Saturation Value'
        huesat.parent = frame

    elif m.type == 'BRIGHT_CONTRAST':

        if ref_tree:
            brightcon_ref = ref_tree.nodes.get(m.brightcon)

        brightcon = new_node(tree, m, 'brightcon', 'ShaderNodeBrightContrast', 'Brightness Contrast')

        if ref_tree:
            copy_node_props(brightcon_ref, brightcon)
            ref_tree.nodes.remove(brightcon_ref)

        links.new(start_rgb.outputs[0], brightcon.inputs[0])
        links.new(brightcon.outputs[0], end_rgb.inputs[0])

        frame.label = 'Brightness Contrast'
        brightcon.parent = frame

    elif m.type == 'MULTIPLIER':

        if ref_tree:
            multiplier_ref = ref_tree.nodes.get(m.multiplier)

        multiplier = new_node(tree, m, 'multiplier', 'ShaderNodeGroup', 'Multiplier')

        if ref_tree:
            copy_node_props(multiplier_ref, multiplier)
            ref_tree.nodes.remove(multiplier_ref)
        else:
            if root_ch.type == 'VALUE':
                multiplier.node_tree = lib.get_node_tree_lib(lib.MOD_MULTIPLIER_VALUE)
            else: multiplier.node_tree = lib.get_node_tree_lib(lib.MOD_MULTIPLIER)

            if BLENDER_28_GROUP_INPUT_HACK:
                duplicate_lib_node_tree(multiplier)

        links.new(start_rgb.outputs[0], multiplier.inputs[0])
        links.new(start_alpha.outputs[0], multiplier.inputs[1])
        links.new(multiplier.outputs[0], end_rgb.inputs[0])
        links.new(multiplier.outputs[1], end_alpha.inputs[0])

        frame.label = 'Multiplier'
        multiplier.parent = frame

def add_new_modifier(parent, modifier_type):

    tl = parent.id_data.tl
    match1 = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', parent.path_from_id())
    match2 = re.match(r'tl\.channels\[(\d+)\]', parent.path_from_id())

    if match1: 
        root_ch = tl.channels[int(match1.group(2))]

    elif match2:
        root_ch = tl.channels[int(match2.group(1))]
    
    tree = get_mod_tree(parent)
    modifiers = parent.modifiers

    # Add new modifier and move it to the top
    m = modifiers.add()
    name = [mt[1] for mt in modifier_type_items if mt[0] == modifier_type][0]
    m.name = get_unique_name(name, modifiers)
    modifiers.move(len(modifiers)-1, 0)
    m = modifiers[0]
    m.type = modifier_type
    #m.channel_type = root_ch.type

    add_modifier_nodes(m, tree)

    if match1: 
        # Enable modifier tree if fine bump map is used
        if parent.normal_map_type == 'FINE_BUMP_MAP' or (
                parent.enable_mask_bump and parent.mask_bump_type == 'FINE_BUMP_MAP'):
            enable_modifiers_tree(parent, False)

    return m

def delete_modifier_nodes(tree, mod):

    # Delete the nodes
    remove_node(tree, mod, 'start_rgb')
    remove_node(tree, mod, 'start_alpha')
    remove_node(tree, mod, 'end_rgb')
    remove_node(tree, mod, 'end_alpha')
    remove_node(tree, mod, 'frame')

    if mod.type == 'RGB_TO_INTENSITY':
        remove_node(tree, mod, 'rgb2i')

    elif mod.type == 'INVERT':
        remove_node(tree, mod, 'invert')

    elif mod.type == 'COLOR_RAMP':
        remove_node(tree, mod, 'color_ramp')
        remove_node(tree, mod, 'color_ramp_linear')
        remove_node(tree, mod, 'color_ramp_alpha_multiply')
        remove_node(tree, mod, 'color_ramp_mix_rgb')
        remove_node(tree, mod, 'color_ramp_mix_alpha')

    elif mod.type == 'RGB_CURVE':
        remove_node(tree, mod, 'rgb_curve')

    elif mod.type == 'HUE_SATURATION':
        remove_node(tree, mod, 'huesat')

    elif mod.type == 'BRIGHT_CONTRAST':
        remove_node(tree, mod, 'brightcon')

    elif mod.type == 'MULTIPLIER':
        remove_node(tree, mod, 'multiplier')

class YNewTexModifier(bpy.types.Operator):
    bl_idname = "node.y_new_texture_modifier"
    bl_label = "New Texture Modifier"
    bl_description = "New Texture Modifier"
    bl_options = {'REGISTER', 'UNDO'}

    type = EnumProperty(
        name = 'Modifier Type',
        items = modifier_type_items,
        default = 'INVERT')

    #parent_type = EnumProperty(
    #        name = 'Modifier Parent',
    #        items = (('CHANNEL', 'Channel', '' ),
    #                 ('TEXTURE_CHANNEL', 'Texture Channel', '' ),
    #                ),
    #        default = 'TEXTURE_CHANNEL')

    @classmethod
    def poll(cls, context):
        return get_active_texture_layers_node() and hasattr(context, 'parent')

    def execute(self, context):
        node = get_active_texture_layers_node()
        group_tree = node.node_tree
        tl = group_tree.tl

        tex = None
        m = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', context.parent.path_from_id())
        if m:
            tex = tl.textures[int(m.group(1))]
            root_ch = tl.channels[int(m.group(2))]
            mod = add_new_modifier(context.parent, self.type)
            tree = get_tree(tex)
            nodes = tree.nodes
        else:
            root_ch = context.parent
            mod = add_new_modifier(context.parent, self.type)
            nodes = group_tree.nodes

        if self.type == 'RGB_TO_INTENSITY' and root_ch.type == 'RGB':
            mod.rgb2i_col = (1,0,1,1)

        # If RGB to intensity is added, bump base is better be 0.0
        if tex and self.type == 'RGB_TO_INTENSITY':
            for i, ch in enumerate(tl.channels):
                c = context.texture.channels[i]
                if ch.type == 'NORMAL':
                    c.bump_base_value = 0.0

        # Expand channel content to see added modifier
        if hasattr(context, 'channel_ui'):
            context.channel_ui.expand_content = True

        # Rearrange nodes
        if tex: 
            rearrange_tex_nodes(tex)
            reconnect_tex_nodes(tex, mod_reconnect=True)
        else: 
            rearrange_tl_nodes(group_tree)
            reconnect_tl_channel_nodes(group_tree, mod_reconnect=True)

        # Reconnect modifier nodes
        #reconnect_between_modifier_nodes(context.parent)

        # Update UI
        context.window_manager.tlui.need_update = True

        return {'FINISHED'}

class YMoveTexModifier(bpy.types.Operator):
    bl_idname = "node.y_move_texture_modifier"
    bl_label = "Move Texture Modifier"
    bl_description = "Move Texture Modifier"
    bl_options = {'REGISTER', 'UNDO'}

    direction = EnumProperty(
            name = 'Direction',
            items = (('UP', 'Up', ''),
                     ('DOWN', 'Down', '')),
            default = 'UP')

    #parent_type = EnumProperty(
    #        name = 'Modifier Parent',
    #        items = (('CHANNEL', 'Channel', '' ),
    #                 ('TEXTURE_CHANNEL', 'Texture Channel', '' ),
    #                ),
    #        default = 'TEXTURE_CHANNEL')

    @classmethod
    def poll(cls, context):
        return (get_active_texture_layers_node() and 
                hasattr(context, 'parent') and hasattr(context, 'modifier'))

    def execute(self, context):
        node = get_active_texture_layers_node()
        group_tree = node.node_tree
        tl = group_tree.tl

        parent = context.parent

        num_mods = len(parent.modifiers)
        if num_mods < 2: return {'CANCELLED'}

        mod = context.modifier
        index = -1
        for i, m in enumerate(parent.modifiers):
            if m == mod:
                index = i
                break
        if index == -1: return {'CANCELLED'}

        # Get new index
        if self.direction == 'UP' and index > 0:
            new_index = index-1
        elif self.direction == 'DOWN' and index < num_mods-1:
            new_index = index+1
        else:
            return {'CANCELLED'}

        tex = context.texture if hasattr(context, 'texture') else None

        if tex: tree = get_tree(tex)
        else: tree = group_tree

        # Swap modifier
        parent.modifiers.move(index, new_index)

        # Reconnect modifier nodes
        reconnect_between_modifier_nodes(parent)

        # Rearrange nodes
        if tex: rearrange_tex_nodes(tex)
        else: rearrange_tl_nodes(group_tree)

        # Update UI
        context.window_manager.tlui.need_update = True

        return {'FINISHED'}

class YRemoveTexModifier(bpy.types.Operator):
    bl_idname = "node.y_remove_texture_modifier"
    bl_label = "Remove Texture Modifier"
    bl_description = "Remove Texture Modifier"
    bl_options = {'REGISTER', 'UNDO'}

    #parent_type = EnumProperty(
    #        name = 'Modifier Parent',
    #        items = (('CHANNEL', 'Channel', '' ),
    #                 ('TEXTURE_CHANNEL', 'Texture Channel', '' ),
    #                ),
    #        default = 'TEXTURE_CHANNEL')

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'parent') and hasattr(context, 'modifier')

    def execute(self, context):
        group_tree = context.parent.id_data
        tl = group_tree.tl

        parent = context.parent
        mod = context.modifier

        index = -1
        for i, m in enumerate(parent.modifiers):
            if m == mod:
                index = i
                break
        if index == -1: return {'CANCELLED'}

        if len(parent.modifiers) < 1: return {'CANCELLED'}

        tex = context.texture if hasattr(context, 'texture') else None

        tree = get_mod_tree(parent)

        # Delete the nodes
        delete_modifier_nodes(tree, mod)

        # Delete the modifier
        parent.modifiers.remove(index)

        if tex and len(parent.modifiers) == 0:
            disable_modifiers_tree(parent, False)
            reconnect_tex_nodes(tex, mod_reconnect=True)
        else:
            # Reconnect nodes
            reconnect_between_modifier_nodes(parent)

        # Rearrange nodes
        if tex:
            rearrange_tex_nodes(tex)
        else: rearrange_tl_nodes(group_tree)

        # Update UI
        context.window_manager.tlui.need_update = True

        return {'FINISHED'}

def draw_modifier_properties(context, root_ch, nodes, modifier, layout):

    #if modifier.type not in {'INVERT'}:
    #    label = [mt[1] for mt in modifier_type_items if modifier.type == mt[0]][0]
    #    layout.label(label + ' Properties:')

    if modifier.type == 'INVERT':
        row = layout.row(align=True)
        invert = nodes.get(modifier.invert)
        if root_ch.type == 'VALUE':
            row.prop(modifier, 'invert_r_enable', text='Value', toggle=True)
            row.prop(modifier, 'invert_a_enable', text='Alpha', toggle=True)
        else:
            row.prop(modifier, 'invert_r_enable', text='R', toggle=True)
            row.prop(modifier, 'invert_g_enable', text='G', toggle=True)
            row.prop(modifier, 'invert_b_enable', text='B', toggle=True)
            row.prop(modifier, 'invert_a_enable', text='A', toggle=True)

    #elif modifier.type == 'RGB_TO_INTENSITY':

    #    # Shortcut only available on texture layer channel
    #    if 'YLayerChannel' in str(type(channel)):
    #        row = layout.row(align=True)
    #        row.label(text='Color Shortcut:')
    #        row.prop(modifier, 'shortcut', text='')

    elif modifier.type == 'COLOR_RAMP':
        color_ramp = nodes.get(modifier.color_ramp)
        layout.template_color_ramp(color_ramp, "color_ramp", expand=True)

    elif modifier.type == 'RGB_CURVE':
        rgb_curve = nodes.get(modifier.rgb_curve)
        rgb_curve.draw_buttons_ext(context, layout)

    elif modifier.type == 'HUE_SATURATION':
        huesat = nodes.get(modifier.huesat)
        row = layout.row(align=True)
        col = row.column(align=True)
        col.label(text='Hue:')
        col.label(text='Saturation:')
        col.label(text='Value:')

        col = row.column(align=True)
        for i in range(3):
            col.prop(huesat.inputs[i], 'default_value', text='')

    elif modifier.type == 'BRIGHT_CONTRAST':
        brightcon = nodes.get(modifier.brightcon)
        row = layout.row(align=True)
        col = row.column(align=True)
        col.label(text='Brightness:')
        col.label(text='Contrast:')

        col = row.column(align=True)
        col.prop(brightcon.inputs[1], 'default_value', text='')
        col.prop(brightcon.inputs[2], 'default_value', text='')

    elif modifier.type == 'MULTIPLIER':
        multiplier = nodes.get(modifier.multiplier)

        col = layout.column(align=True)
        row = col.row()
        row.label(text='Clamp:')
        row.prop(modifier, 'use_clamp', text='')
        if root_ch.type == 'VALUE':
            #col.prop(multiplier.inputs[3], 'default_value', text='Value')
            #col.prop(multiplier.inputs[4], 'default_value', text='Alpha')
            col.prop(modifier, 'multiplier_r_val', text='Value')
            col.prop(modifier, 'multiplier_a_val', text='Alpha')
        else:
            #col.prop(multiplier.inputs[3], 'default_value', text='R')
            #col.prop(multiplier.inputs[4], 'default_value', text='G')
            #col.prop(multiplier.inputs[5], 'default_value', text='B')
            col.prop(modifier, 'multiplier_r_val', text='R')
            col.prop(modifier, 'multiplier_g_val', text='G')
            col.prop(modifier, 'multiplier_b_val', text='B')
            #col = layout.column(align=True)
            col.separator()
            #col.prop(multiplier.inputs[6], 'default_value', text='Alpha')
            col.prop(modifier, 'multiplier_a_val', text='Alpha')

class YTexModifierSpecialMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_texture_modifier_specials"
    bl_label = "Texture Channel Modifiers"
    bl_description = 'Add New Modifier'

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'parent') and get_active_texture_layers_node()

    def draw(self, context):
        self.layout.label(text='Add Modifier')
        ## List the items
        for mt in modifier_type_items:
            self.layout.operator('node.y_new_texture_modifier', text=mt[1], icon='MODIFIER').type = mt[0]

def update_modifier_enable(self, context):

    tree = get_mod_tree(self)
    nodes = tree.nodes

    if self.type == 'RGB_TO_INTENSITY':
        rgb2i = nodes.get(self.rgb2i)
        rgb2i.mute = not self.enable

    elif self.type == 'INVERT':
        invert = nodes.get(self.invert)
        invert.mute = not self.enable

    elif self.type == 'COLOR_RAMP':
        color_ramp = nodes.get(self.color_ramp)
        color_ramp.mute = not self.enable
        color_ramp_linear = nodes.get(self.color_ramp_linear)
        color_ramp_linear.mute = not self.enable
        color_ramp_alpha_multiply = nodes.get(self.color_ramp_alpha_multiply)
        color_ramp_alpha_multiply.mute = not self.enable
        color_ramp_mix_rgb = nodes.get(self.color_ramp_mix_rgb)
        color_ramp_mix_rgb.mute = not self.enable
        color_ramp_mix_alpha = nodes.get(self.color_ramp_mix_alpha)
        color_ramp_mix_alpha.mute = not self.enable

    elif self.type == 'RGB_CURVE':
        rgb_curve = nodes.get(self.rgb_curve)
        rgb_curve.mute = not self.enable

    elif self.type == 'HUE_SATURATION':
        huesat = nodes.get(self.huesat)
        huesat.mute = not self.enable

    elif self.type == 'BRIGHT_CONTRAST':
        brightcon = nodes.get(self.brightcon)
        brightcon.mute = not self.enable

    elif self.type == 'MULTIPLIER':
        multiplier = nodes.get(self.multiplier)
        multiplier.mute = not self.enable

def update_modifier_shortcut(self, context):
    tl = self.id_data.tl

    if self.shortcut:
        mod_found = False
        # Check if modifier on group channel
        channel = tl.channels[tl.active_channel_index]
        for mod in channel.modifiers:
            if mod == self:
                mod_found = True
                break

        if mod_found:
            # Disable other shortcuts
            for mod in channel.modifiers:
                if mod != self: mod.shortcut = False
            return

        # Check texture channels
        tex = tl.textures[tl.active_texture_index]
        for ch in tex.channels:
            for mod in ch.modifiers:
                if mod != self:
                    mod.shortcut = False

def update_invert_channel(self, context):

    tl = self.id_data.tl
    match1 = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]\.modifiers\[(\d+)\]', self.path_from_id())
    match2 = re.match(r'tl\.channels\[(\d+)\]\.modifiers\[(\d+)\]', self.path_from_id())
    if match1: 
        root_ch = tl.channels[int(match1.group(2))]
    elif match2:
        root_ch = tl.channels[int(match2.group(1))]

    tree = get_mod_tree(self)
    invert = tree.nodes.get(self.invert)

    if self.invert_r_enable:
        invert.inputs[2].default_value = 1.0
    else: invert.inputs[2].default_value = 0.0

    if root_ch.type == 'VALUE':

        if self.invert_a_enable:
            invert.inputs[3].default_value = 1.0
        else: invert.inputs[3].default_value = 0.0

    else:

        if self.invert_g_enable:
            invert.inputs[3].default_value = 1.0
        else: invert.inputs[3].default_value = 0.0

        if self.invert_b_enable:
            invert.inputs[4].default_value = 1.0
        else: invert.inputs[4].default_value = 0.0

        if self.invert_a_enable:
            invert.inputs[5].default_value = 1.0
        else: invert.inputs[5].default_value = 0.0

    if BLENDER_28_GROUP_INPUT_HACK:
        match_group_input(invert)
        #inp = invert.node_tree.nodes.get('Group Input')

        #if root_ch.type == 'VALUE':
        #    end = 4
        #else: end = 6

        #for i in range(2, end):
        #    for link in inp.outputs[i].links:
        #        if link.to_socket.default_value != invert.inputs[i].default_value:
        #            link.to_socket.default_value = invert.inputs[i].default_value

def update_use_clamp(self, context):
    tree = get_mod_tree(self)

    if self.type == 'MULTIPLIER':
        multiplier = tree.nodes.get(self.multiplier)
        multiplier.inputs[2].default_value = 1.0 if self.use_clamp else 0.0

        if BLENDER_28_GROUP_INPUT_HACK:
            match_group_input(multiplier, 2)
            #inp = multiplier.node_tree.nodes.get('Group Input')
            #if inp.outputs[2].links[0].to_socket.default_value != multiplier.inputs[2].default_value:
            #    inp.outputs[2].links[0].to_socket.default_value = multiplier.inputs[2].default_value

def update_multiplier_val_input(self, context):
    tl = self.id_data.tl
    match1 = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]\.modifiers\[(\d+)\]', self.path_from_id())
    match2 = re.match(r'tl\.channels\[(\d+)\]\.modifiers\[(\d+)\]', self.path_from_id())
    if match1: 
        root_ch = tl.channels[int(match1.group(2))]
    elif match2:
        root_ch = tl.channels[int(match2.group(1))]

    tree = get_mod_tree(self)

    if self.type == 'MULTIPLIER':
        multiplier = tree.nodes.get(self.multiplier)
        multiplier.inputs[3].default_value = self.multiplier_r_val
        if root_ch.type == 'VALUE':
            multiplier.inputs[4].default_value = self.multiplier_a_val
        else:
            multiplier.inputs[4].default_value = self.multiplier_g_val
            multiplier.inputs[5].default_value = self.multiplier_b_val
            multiplier.inputs[6].default_value = self.multiplier_a_val

        if BLENDER_28_GROUP_INPUT_HACK:
            match_group_input(multiplier)
            #inp = multiplier.node_tree.nodes.get('Group Input')
            #if root_ch.type == 'VALUE':
            #    end = 5
            #else: end = 7
            #for i in range(3, end):
            #    for link in inp.outputs[i].links:
            #        if link.to_socket.default_value != multiplier.inputs[i].default_value:
            #            link.to_socket.default_value = multiplier.inputs[i].default_value

def update_rgb2i_col(self, context):
    tree = get_mod_tree(self)

    if self.type == 'RGB_TO_INTENSITY':
        rgb2i = tree.nodes.get(self.rgb2i)
        rgb2i.inputs[2].default_value = self.rgb2i_col

        if BLENDER_28_GROUP_INPUT_HACK:
            match_group_input(rgb2i, 2)
            #inp = rgb2i.node_tree.nodes.get('Group Input')
            #inp.outputs[2].links[0].to_socket.default_value = self.rgb2i_col

class YTextureModifier(bpy.types.PropertyGroup):
    enable = BoolProperty(default=True, update=update_modifier_enable)
    name = StringProperty(default='')

    #channel_type = StringProperty(default='')

    type = EnumProperty(
        name = 'Modifier Type',
        items = modifier_type_items,
        default = 'INVERT')

    # Base nodes
    start_rgb = StringProperty(default='')
    start_alpha = StringProperty(default='')
    end_rgb = StringProperty(default='')
    end_alpha = StringProperty(default='')

    # RGB to Intensity nodes
    rgb2i = StringProperty(default='')

    rgb2i_col = FloatVectorProperty(name='RGB to Intensity Color', size=4, subtype='COLOR', 
            default=(1.0,1.0,1.0,1.0), min=0.0, max=1.0,
            update=update_rgb2i_col)

    # Invert nodes
    invert = StringProperty(default='')

    # Invert toggles
    invert_r_enable = BoolProperty(default=True, update=update_invert_channel)
    invert_g_enable = BoolProperty(default=True, update=update_invert_channel)
    invert_b_enable = BoolProperty(default=True, update=update_invert_channel)
    invert_a_enable = BoolProperty(default=False, update=update_invert_channel)

    # Mask nodes
    #mask_texture = StringProperty(default='')

    # Color Ramp nodes
    color_ramp = StringProperty(default='')
    color_ramp_linear = StringProperty(default='')
    color_ramp_alpha_multiply = StringProperty(default='')
    color_ramp_mix_rgb = StringProperty(default='')
    color_ramp_mix_alpha = StringProperty(default='')

    # RGB Curve nodes
    rgb_curve = StringProperty(default='')

    # Brightness Contrast nodes
    brightcon = StringProperty(default='')

    # Hue Saturation nodes
    huesat = StringProperty(default='')

    # Multiplier nodes
    multiplier = StringProperty(default='')

    multiplier_r_val = FloatProperty(default=1.0, update=update_multiplier_val_input)
    multiplier_g_val = FloatProperty(default=1.0, update=update_multiplier_val_input)
    multiplier_b_val = FloatProperty(default=1.0, update=update_multiplier_val_input)
    multiplier_a_val = FloatProperty(default=1.0, update=update_multiplier_val_input)

    # Individual modifier node frame
    frame = StringProperty(default='')

    # Clamp prop is available in some modifiers
    use_clamp = BoolProperty(name='Use Clamp', default=False, update=update_use_clamp)

    shortcut = BoolProperty(
            name = 'Property Shortcut',
            description = 'Property shortcut on texture list (currently only available on RGB to Intensity)',
            default=False,
            update=update_modifier_shortcut)

    expand_content = BoolProperty(default=True)

def set_modifiers_tree_per_directions(tree, ch, mod_tree):

    if ch.normal_map_type == 'FINE_BUMP_MAP':
        for d in neighbor_directions:
            m = tree.nodes.get(getattr(ch, 'mod_' + d))
            if not m:
                m = new_node(tree, ch, 'mod_' + d, 'ShaderNodeGroup', 'mod ' + d)
                m.node_tree = mod_tree
                m.hide = True

    if ch.enable_mask_bump and ch.mask_bump_type == 'FINE_BUMP_MAP':
        for d in neighbor_directions:
            m = tree.nodes.get(getattr(ch, 'mb_mod_' + d))
            if not m:
                m = new_node(tree, ch, 'mb_mod_' + d, 'ShaderNodeGroup', 'mb_mod ' + d)
                m.node_tree = mod_tree
                m.hide = True

def unset_modifiers_tree_per_directions(tree, ch):
    for d in neighbor_directions:
        remove_node(tree, ch, 'mod_' + d)
        remove_node(tree, ch, 'mb_mod_' + d)

def enable_modifiers_tree(ch, rearrange = True):
    
    group_tree = ch.id_data
    tl = group_tree.tl

    m = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', ch.path_from_id())
    if not m: return
    tex = tl.textures[int(m.group(1))]
    root_ch = tl.channels[int(m.group(2))]

    tex_tree = get_tree(tex)

    # Check if modifier tree already available
    if ch.mod_group != '': 
        mod_group = tex_tree.nodes.get(ch.mod_group)
        mod_tree = mod_group.node_tree
        set_modifiers_tree_per_directions(tex_tree, ch, mod_tree)
        return mod_tree

    if len(ch.modifiers) == 0:
        return None

    mod_tree = bpy.data.node_groups.new('~TL Modifiers ' + root_ch.name + ' ' + tex.name, 'ShaderNodeTree')

    mod_tree.inputs.new('NodeSocketColor', 'RGB')
    mod_tree.inputs.new('NodeSocketFloat', 'Alpha')
    mod_tree.outputs.new('NodeSocketColor', 'RGB')
    mod_tree.outputs.new('NodeSocketFloat', 'Alpha')

    # New inputs and outputs
    mod_tree_start = mod_tree.nodes.new('NodeGroupInput')
    mod_tree_start.name = MODIFIER_TREE_START
    mod_tree_end = mod_tree.nodes.new('NodeGroupOutput')
    mod_tree_end.name = MODIFIER_TREE_END

    mod_group = new_node(tex_tree, ch, 'mod_group', 'ShaderNodeGroup', tex.name + ' ' + ch.name + ' Modifiers')
    mod_group.node_tree = mod_tree

    for mod in ch.modifiers:
        add_modifier_nodes(mod, mod_tree, tex_tree)

    set_modifiers_tree_per_directions(tex_tree, ch, mod_tree)

    if rearrange:
        rearrange_tex_nodes(tex)
        reconnect_between_modifier_nodes(ch)

    return mod_tree

def disable_modifiers_tree(ch, rearrange=True):
    group_tree = ch.id_data
    tl = group_tree.tl

    m = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', ch.path_from_id())
    if not m: return
    tex = tl.textures[int(m.group(1))]
    ch_index = int(m.group(2))
    tex_tree = get_tree(tex)

    unset_modifiers_tree_per_directions(tex_tree, ch)

    # Check if fine bump map is still used
    if len(ch.modifiers) > 0 and tl.channels[ch_index].type == 'NORMAL' and (ch.normal_map_type == 'FINE_BUMP_MAP' 
            or ch.mask_bump_type == 'FINE_BUMP_MAP'):
        return

    # Check if channel use blur
    if hasattr(ch, 'enable_blur') and ch.enable_blur:
        return

    # Check if modifier tree already gone
    if ch.mod_group == '': return

    # Get modifier group
    mod_group = tex_tree.nodes.get(ch.mod_group)

    # Check if texture channels has fine bump
    #fine_bump_found = False
    #for i, ch in enumerate(tex.channels):
    #    if tl.channels[i].type == 'NORMAL' and ch.normal_map_type == 'FINE_BUMP_MAP':
    #        fine_bump_found = True

    #if fine_bump_found: return

    # Add new copied modifier nodes on texture tree
    for mod in ch.modifiers:
        add_modifier_nodes(mod, tex_tree, mod_group.node_tree)

    # Remove modifier tree
    bpy.data.node_groups.remove(mod_group.node_tree)
    remove_node(tex_tree, ch, 'mod_group')

    unset_modifiers_tree_per_directions(tex_tree, ch)

    if rearrange:
        reconnect_between_modifier_nodes(ch)
        rearrange_tex_nodes(tex)

def register():
    bpy.utils.register_class(YNewTexModifier)
    bpy.utils.register_class(YMoveTexModifier)
    bpy.utils.register_class(YRemoveTexModifier)
    bpy.utils.register_class(YTexModifierSpecialMenu)
    bpy.utils.register_class(YTextureModifier)

def unregister():
    bpy.utils.unregister_class(YNewTexModifier)
    bpy.utils.unregister_class(YMoveTexModifier)
    bpy.utils.unregister_class(YRemoveTexModifier)
    bpy.utils.unregister_class(YTexModifierSpecialMenu)
    bpy.utils.unregister_class(YTextureModifier)
